from datetime import datetime
from decimal import Decimal

import structlog
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
