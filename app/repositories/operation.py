from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.repositories.base import BaseRepository
from app.models.operation import Operation, Event, SubmitIntent
from app.constants import EventType, IntentStatus, OperationStatus
from app.core.database.engine import async_session_maker


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
        """
        Атомарное создание операции с событием CREATED
        """
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
                )
                session.add(event)

                await session.flush()
                await session.refresh(operation)

        return operation

    @classmethod
    async def submit_operation(cls, operation_id: str) -> tuple[Operation, bool]:
        """
        Атомарное создание намерения отправки и перевод операции в PROCESSING.
        """
        async with async_session_maker() as session:
            async with session.begin():
                # Блокируем операцию для обновления
                stmt = select(Operation).where(
                    Operation.id == operation_id).with_for_update()
                result = await session.execute(stmt)
                operation = result.scalar_one_or_none()

                if operation is None:
                    raise ValueError(f"Operation {operation_id} not found")

                # Проверяем существование намерения
                intent_stmt = select(SubmitIntent).where(
                    SubmitIntent.operation_id == operation_id)
                intent_result = await session.execute(intent_stmt)
                existing_intent = intent_result.scalar_one_or_none()

                # Если намерение уже существует, возвращаем текущее состояние
                if existing_intent is not None:
                    return operation, False

                if operation.status != OperationStatus.CREATED:
                    return operation, False

                intent = SubmitIntent(
                    operation_id=operation_id,
                    status=IntentStatus.PENDING,
                    attempt_count=0,
                )
                session.add(intent)

                operation.status = OperationStatus.PROCESSING

                event = Event(
                    operation_id=operation_id,
                    event_type=EventType.SUBMIT_REQUESTED,
                    from_status=OperationStatus.CREATED,
                    to_status=OperationStatus.PROCESSING,
                )
                session.add(event)

                await session.flush()
                await session.refresh(operation)

        return operation, True
