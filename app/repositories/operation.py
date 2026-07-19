from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID
import structlog
from app.core.metrics import (
    payments_submit_attempts_total,
    payments_submit_retries_total,
    payments_stale_intents_reset_total,
)

from sqlalchemy import and_, func, or_, select

from app.constants import CallbackResult, EventType, IntentStatus, OperationStatus
from app.core.config import settings
from app.core.database.engine import async_session_maker
from app.models.operation import Event, Operation, ProcessedCallback, SubmitIntent
from app.repositories.base import BaseRepository

logger = structlog.get_logger()


class OperationRepository(BaseRepository):
    model = Operation

    @classmethod
    async def create_with_event(
        cls,
        operation_id: str,
        amount: Decimal,
        currency: str,
        description: str | None,
    ) -> Operation:
        """Атомарно создать операцию и событие CREATED."""
        async with async_session_maker() as session:
            async with session.begin():
                operation = Operation(
                    id=operation_id,
                    amount=amount,
                    currency=currency,
                    description=description,
                    status=OperationStatus.CREATED,
                )
                session.add(operation)

                event = Event(
                    operation_id=operation_id,
                    event_type=EventType.CREATED,
                    from_status=None,
                    to_status=OperationStatus.CREATED,
                    message='Operation created',
                )
                session.add(event)

                await session.flush()
                await session.refresh(operation)

        return operation

    @classmethod
    async def get_operation(cls, operation_id: str) -> Operation | None:
        async with async_session_maker() as session:
            stmt = select(Operation).where(Operation.id == operation_id)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    @classmethod
    async def submit_operation(cls, operation_id: str) -> tuple[Operation, bool]:
        """Создать намерение отправки и перевести операцию в PROCESSING, если она всё ещё в CREATED."""
        async with async_session_maker() as session:
            async with session.begin():
                stmt = select(Operation).where(
                    Operation.id == operation_id).with_for_update()
                result = await session.execute(stmt)
                operation = result.scalar_one_or_none()

                if operation is None:
                    raise ValueError(f'Operation {operation_id} not found')

                intent_stmt = select(SubmitIntent).where(
                    SubmitIntent.operation_id == operation_id)
                intent_result = await session.execute(intent_stmt)
                existing_intent = intent_result.scalar_one_or_none()

                if existing_intent is not None or operation.status != OperationStatus.CREATED:
                    return operation, False

                intent = SubmitIntent(
                    operation_id=operation_id,
                    status=IntentStatus.PENDING,
                    attempt_count=0,
                    next_retry_at=datetime.now(),
                )
                session.add(intent)

                operation.status = OperationStatus.PROCESSING

                event = Event(
                    operation_id=operation_id,
                    event_type=EventType.SUBMIT_REQUESTED,
                    from_status=OperationStatus.CREATED,
                    to_status=OperationStatus.PROCESSING,
                    message='Submit requested',
                )
                session.add(event)

                await session.flush()
                await session.refresh(operation)

        return operation, True

    @classmethod
    async def get_pending_intents(cls) -> list[SubmitIntent]:
        async with async_session_maker() as session:
            now = datetime.now()
            stmt = (
                select(SubmitIntent)
                .join(Operation, Operation.id == SubmitIntent.operation_id)
                .where(
                    and_(
                        SubmitIntent.status.in_(
                            [IntentStatus.PENDING, IntentStatus.FAILED]),
                        or_(
                            SubmitIntent.next_retry_at.is_(None),
                            SubmitIntent.next_retry_at <= now,
                        ),
                    )
                )
                .order_by(SubmitIntent.id.asc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    @classmethod
    async def get_processing_operations_without_intent(cls) -> list[Operation]:
        async with async_session_maker() as session:
            intent_subquery = select(SubmitIntent.operation_id).distinct()
            stmt = (
                select(Operation)
                .where(
                    and_(
                        Operation.status == OperationStatus.PROCESSING,
                        Operation.id.not_in(intent_subquery),
                    )
                )
                .order_by(Operation.id.asc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    @classmethod
    async def get_stale_processing_intents(cls, stale_seconds: float) -> list[SubmitIntent]:
        async with async_session_maker() as session:
            cutoff = datetime.now() - \
                timedelta(seconds=stale_seconds)
            stmt = (
                select(SubmitIntent)
                .where(
                    and_(
                        SubmitIntent.status == IntentStatus.PROCESSING,
                        SubmitIntent.updated_at < cutoff,
                    )
                )
                .order_by(SubmitIntent.id.asc())
            )
            result = await session.execute(stmt)
            return list(result.scalars().all())

    @classmethod
    async def reset_stale_processing_intent(cls, intent_id: int) -> SubmitIntent | None:
        async with async_session_maker() as session:
            async with session.begin():
                stmt = select(SubmitIntent).where(
                    SubmitIntent.id == intent_id).with_for_update()
                result = await session.execute(stmt)
                intent = result.scalar_one_or_none()
                if intent is None or intent.status != IntentStatus.PROCESSING:
                    return None

                if intent.attempt_count >= settings.RETRY_MAX_ATTEMPTS:
                    logger.info(
                        'stale_intent_reset',
                        operation_id=intent.operation_id,
                        attempt=intent.attempt_count,
                        status='ABANDONED',
                    )
                    return await cls._mark_submit_abandoned_in_session(session, intent)

                logger.info(
                    'stale_intent_reset',
                    operation_id=intent.operation_id,
                    attempt=intent.attempt_count,
                    status='FAILED',
                )
                intent.status = IntentStatus.FAILED
                intent.next_retry_at = datetime.now()
                intent.updated_at = datetime.now()
                payments_stale_intents_reset_total.inc()
                await session.flush()
                return intent

    @classmethod
    async def _mark_submit_abandoned_in_session(cls, session, intent: SubmitIntent) -> SubmitIntent:
        operation_stmt = select(Operation).where(
            Operation.id == intent.operation_id).with_for_update()
        operation_result = await session.execute(operation_stmt)
        operation = operation_result.scalar_one_or_none()
        if operation is None:
            return intent

        intent.status = IntentStatus.ABANDONED
        payments_stale_intents_reset_total.inc()
        intent.next_retry_at = None
        intent.updated_at = datetime.now()

        if operation.status not in {OperationStatus.COMPLETED, OperationStatus.REJECTED}:
            previous_status = operation.status
            operation.status = OperationStatus.REJECTED
            event = Event(
                operation_id=operation.id,
                event_type=EventType.SUBMIT_ABANDONED,
                from_status=previous_status,
                to_status=OperationStatus.REJECTED,
                message='Submit abandoned after max retry attempts',
            )
            session.add(event)

        await session.flush()
        return intent

    @classmethod
    async def mark_submit_abandoned(cls, intent_id: int) -> SubmitIntent | None:
        async with async_session_maker() as session:
            async with session.begin():
                stmt = select(SubmitIntent).where(
                    SubmitIntent.id == intent_id).with_for_update()
                result = await session.execute(stmt)
                intent = result.scalar_one_or_none()
                if intent is None:
                    return None

                return await cls._mark_submit_abandoned_in_session(session, intent)

    @classmethod
    async def start_submit_attempt(cls, intent_id: int) -> SubmitIntent | None:
        async with async_session_maker() as session:
            async with session.begin():
                stmt = select(SubmitIntent).where(
                    SubmitIntent.id == intent_id).with_for_update()
                result = await session.execute(stmt)
                intent = result.scalar_one_or_none()
                if intent is None:
                    return None

                intent.status = IntentStatus.PROCESSING
                intent.attempt_count += 1
                payments_submit_attempts_total.inc()
                intent.updated_at = datetime.now()
                await session.flush()
                return intent

    @classmethod
    async def mark_submit_success(cls, intent_id: int, provider_payment_id: str | None) -> Operation | None:
        async with async_session_maker() as session:
            async with session.begin():
                intent_stmt = select(SubmitIntent).where(
                    SubmitIntent.id == intent_id).with_for_update()
                intent_result = await session.execute(intent_stmt)
                intent = intent_result.scalar_one_or_none()
                if intent is None:
                    return None

                operation_stmt = select(Operation).where(
                    Operation.id == intent.operation_id).with_for_update()
                operation_result = await session.execute(operation_stmt)
                operation = operation_result.scalar_one_or_none()
                if operation is None:
                    return None

                if intent.status == IntentStatus.COMPLETED:
                    return operation

                intent.status = IntentStatus.COMPLETED
                intent.next_retry_at = None
                intent.updated_at = datetime.now()

                if provider_payment_id and operation.provider_payment_id is None:
                    operation.provider_payment_id = UUID(provider_payment_id)

                if operation.status == OperationStatus.PROCESSING:
                    event = Event(
                        operation_id=operation.id,
                        event_type=EventType.PROVIDER_RESPONSE_RECEIVED,
                        from_status=operation.status,
                        to_status=operation.status,
                        message='Provider response received',
                    )
                    session.add(event)

                await session.flush()
                await session.refresh(operation)
                return operation

    @classmethod
    async def mark_submit_retry(cls, intent_id: int, retry_delay_seconds: float) -> SubmitIntent | None:
        async with async_session_maker() as session:
            async with session.begin():
                stmt = select(SubmitIntent).where(
                    SubmitIntent.id == intent_id).with_for_update()
                result = await session.execute(stmt)
                intent = result.scalar_one_or_none()
                if intent is None:
                    return None

                if intent.attempt_count >= settings.RETRY_MAX_ATTEMPTS:
                    return await cls._mark_submit_abandoned_in_session(session, intent)

                intent.status = IntentStatus.FAILED
                intent.next_retry_at = datetime.now() + timedelta(seconds=retry_delay_seconds)
                payments_submit_retries_total.labels(
                    reason="provider_error",
                ).inc()
                intent.updated_at = datetime.now()
                await session.flush()
                return intent

    @classmethod
    async def handle_receipt(
        cls,
        operation_id: str,
        provider_payment_id: str,
        result: CallbackResult,
        message: str | None,
    ) -> tuple[Operation, bool]:
        async with async_session_maker() as session:
            async with session.begin():
                stmt = select(Operation).where(
                    Operation.id == operation_id).with_for_update()
                result_row = await session.execute(stmt)
                operation = result_row.scalar_one_or_none()
                if operation is None:
                    raise ValueError(f'Operation {operation_id} not found')

                callback_stmt = select(ProcessedCallback).where(
                    ProcessedCallback.operation_id == operation_id,
                    ProcessedCallback.provider_payment_id == provider_payment_id,
                )
                callback_result = await session.execute(callback_stmt)
                existing_callback = callback_result.scalar_one_or_none()
                if existing_callback is not None:
                    return operation, False

                provider_payment_uuid = UUID(provider_payment_id)
                if operation.provider_payment_id is None:
                    operation.provider_payment_id = provider_payment_uuid
                elif operation.provider_payment_id != provider_payment_uuid:
                    raise RuntimeError('Provider payment id mismatch')

                if operation.status in {OperationStatus.COMPLETED, OperationStatus.REJECTED}:
                    return operation, False

                final_status = OperationStatus.COMPLETED if result == CallbackResult.COMPLETED else OperationStatus.REJECTED
                previous_status = operation.status
                operation.status = final_status
                callback = ProcessedCallback(
                    provider_payment_id=provider_payment_id,
                    operation_id=operation_id,
                    result=result,
                    processed_at=datetime.now(),
                )
                session.add(callback)

                event = Event(
                    operation_id=operation_id,
                    event_type=EventType.CALLBACK_RECEIVED,
                    from_status=previous_status,
                    to_status=final_status,
                    message=message or 'Receipt processed',
                )
                session.add(event)

                await session.flush()
                await session.refresh(operation)
                return operation, True

    @classmethod
    async def count_pending_intents(cls) -> int:
        async with async_session_maker() as session:
            stmt = (
                select(func.count())
                .select_from(SubmitIntent)
                .where(
                    SubmitIntent.status == IntentStatus.PENDING
                )
            )

            result = await session.execute(stmt)
            return result.scalar_one()

    @classmethod
    async def count_processing_operations(cls) -> int:
        async with async_session_maker() as session:
            stmt = (
                select(func.count())
                .select_from(Operation)
                .where(
                    Operation.status == OperationStatus.PROCESSING
                )
            )

            result = await session.execute(stmt)
            return result.scalar_one()
