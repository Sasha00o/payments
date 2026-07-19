from __future__ import annotations

import asyncio
from decimal import Decimal

import structlog
from fastapi import status
from sqlalchemy.exc import IntegrityError
from app.core.logger import bind_context, clear_context

from app.constants import OperationStatus
from app.core.config import settings
from app.core.retry import compute_retry_delay
from app.models import CreateOperationRequest, Event, Operation, ReceiptRequest
from app.repositories import EventRepository, OperationRepository
from app.services.provider import ProviderService
from app.services.receipt import ReceiptService
from app.core.metrics import (
    payments_pending_intents,
    payments_processing_operations,
)

logger = structlog.get_logger()


class OperationService:
    """Сервис для управления жизненным циклом операций."""

    @staticmethod
    async def create_operation(request: CreateOperationRequest) -> Operation:
        try:
            operation = await OperationRepository.create_with_event(
                operation_id=request.operationId,
                amount=Decimal(request.amount),
                currency=request.currency,
                description=request.description,
            )

            logger.info(
                'operation_created',
                operation_id=request.operationId,
                amount=request.amount,
                currency=request.currency,
            )
            return operation
        except IntegrityError:
            logger.warning('operation_duplicate',
                           operation_id=request.operationId)
            raise

    @staticmethod
    async def get_operation(operation_id: str) -> Operation | None:
        return await OperationRepository.get_operation(operation_id)

    @staticmethod
    async def submit_operation(operation_id: str) -> tuple[Operation, int]:
        try:
            operation, intent_created = await OperationRepository.submit_operation(operation_id)
            if intent_created:
                logger.info('submit_intent_created',
                            operation_id=operation_id, status=operation.status)
                return operation, status.HTTP_202_ACCEPTED

            logger.info('submit_idempotent',
                        operation_id=operation_id, status=operation.status)
            return operation, status.HTTP_200_OK
        except ValueError:
            logger.error('submit_operation_not_found',
                         operation_id=operation_id)
            raise

    @staticmethod
    async def handle_receipt(request: ReceiptRequest) -> tuple[Operation, int]:
        return await ReceiptService.handle(request)

    @staticmethod
    async def get_conversion_history(operation_id: str) -> list[Event]:
        try:
            events = await EventRepository.get_operation_events(operation_id)
            logger.info('operation_history_retrieved',
                        operation_id=operation_id, events_count=len(events))
            return events
        except ValueError:
            logger.error('event_for_this_operation_not_found',
                         operation_id=operation_id)
            raise

    @staticmethod
    async def process_pending_submissions() -> None:
        stale_intents = await OperationRepository.get_stale_processing_intents(
            settings.INTENT_STALE_SECONDS
        )

        for intent in stale_intents:
            await OperationRepository.reset_stale_processing_intent(
                intent.id
            )

        intents = await OperationRepository.get_pending_intents()
        for intent in intents:
            operation = await OperationRepository.get_operation(intent.operation_id)
            if operation is None:
                continue
            if operation.status in {OperationStatus.COMPLETED, OperationStatus.REJECTED}:
                await OperationRepository.mark_submit_success(intent.id, None)
                continue

            intent = await OperationRepository.start_submit_attempt(intent.id)

            if intent is None:
                continue

            bind_context(
                operation_id=operation.id,
                intent_id=intent.id,
                attempt=intent.attempt_count,
            )

            try:
                await ProviderService.submit(operation, intent)

            except Exception as exc:
                logger.exception(
                    "submit_attempt_failed",
                    error=str(exc),
                    attempt=intent.attempt_count,
                )

                await OperationRepository.mark_submit_retry(
                    intent.id,
                    retry_delay_seconds=compute_retry_delay(
                        intent.attempt_count
                    ),
                )

            finally:
                clear_context()

        recovered_operations = (
            await OperationRepository.get_processing_operations_without_intent()
        )

        for operation in recovered_operations:
            recovered_intent = await OperationRepository.submit_operation(
                operation.id
            )

            if recovered_intent is None:
                continue

            recovered_intent = await OperationRepository.start_submit_attempt(
                recovered_intent.id
            )

            if recovered_intent is None:
                continue

            bind_context(
                operation_id=operation.id,
                intent_id=recovered_intent.id,
                attempt=recovered_intent.attempt_count,
            )

            try:
                await ProviderService.submit(
                    operation,
                    recovered_intent
                )

            except Exception as exc:
                logger.exception(
                    "recovered_submit_attempt_failed",
                    error=str(exc),
                )

                await OperationRepository.mark_submit_retry(
                    recovered_intent.id,
                    retry_delay_seconds=compute_retry_delay(
                        recovered_intent.attempt_count
                    ),
                )

            finally:
                clear_context()

    @staticmethod
    async def update_metrics() -> None:
        pending_intents = await OperationRepository.count_pending_intents()
        processing_operations = await OperationRepository.count_processing_operations()

        payments_pending_intents.set(pending_intents)
        payments_processing_operations.set(processing_operations)


async def run_submission_worker(shutdown_event: asyncio.Event) -> None:
    logger.info('submission_worker_started')
    while not shutdown_event.is_set():
        try:
            await OperationService.process_pending_submissions()
        except Exception as exc:  # pragma: no cover - служебный защитный обработчик
            logger.exception('submission_worker_failed', error=str(exc))
        
        try:
            await asyncio.wait_for(
                shutdown_event.wait(),
                timeout=settings.WORKER_POLL_INTERVAL,
            )
        except asyncio.TimeoutError:
            pass
    
    logger.info('submission_worker_stopping')
    logger.info('submission_worker_stopped')


async def run_metrics_worker() -> None:
    while True:
        try:
            await OperationService.update_metrics()
        except Exception as exc:
            logger.exception('metrics_worker_failed', error=str(exc))

        await asyncio.sleep(settings.METRICS_POLL_INTERVAL)
