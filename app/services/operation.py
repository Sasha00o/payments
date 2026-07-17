from app.repositories.event import EventRepository
from datetime import datetime
from decimal import Decimal

import structlog
from fastapi import status
from sqlalchemy.exc import IntegrityError

from app.constants import EventType, OperationStatus
from app.models import CreateOperationRequest, Event, Operation
from app.repositories import OperationRepository


logger = structlog.get_logger()


class OperationService:
    """Сервис для работы с операциями"""

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
                "operation_created",
                operation_id=request.operationId,
                amount=request.amount,
                currency=request.currency,
            )

            return operation

        except IntegrityError:
            logger.warning(
                "operation_duplicate",
                operation_id=request.operationId,
            )
            raise

    @staticmethod
    async def get_operation(operation_id: str) -> Operation | None:
        """
        Получение операции по ID
        """
        return await OperationRepository.find_by_id(operation_id)

    @staticmethod
    async def submit_operation(operation_id: str) -> tuple[Operation, int]:
        """
        Отправка операции провайдеру.
        """
        try:
            operation, intent_created = await OperationRepository.submit_operation(operation_id)

            if intent_created:
                logger.info(
                    "submit_intent_created",
                    operation_id=operation_id,
                    status=operation.status,
                )
                return operation, status.HTTP_202_ACCEPTED
            else:
                logger.info(
                    "submit_idempotent",
                    operation_id=operation_id,
                    status=operation.status,
                )
                return operation, status.HTTP_200_OK

        except ValueError:
            logger.error("submit_operation_not_found",
                         operation_id=operation_id)
            raise

    @staticmethod
    async def get_conversion_history(operation_id: str) -> list[Event]:
        """
        Получение всех событий операции, отсортированных по event_id
        """
        try:
            events = await EventRepository.get_operation_events(operation_id)

            logger.info(
                "operation_history_retrieved",
                operation_id=operation_id,
                events_count=len(events),
            )

            return events
        except ValueError:
            logger.error(
                "event_for_this_operation_not_found",
                operation_id=operation_id,
            )
            raise
