from __future__ import annotations

import structlog
from fastapi import status

from app.models import Operation, ReceiptRequest
from app.repositories import OperationRepository

logger = structlog.get_logger()


class ReceiptService:
    """Сервис для обработки callback-квитанций провайдера."""

    @staticmethod
    async def handle(request: ReceiptRequest) -> tuple[Operation, int]:
        try:
            operation, changed = await OperationRepository.handle_receipt(
                operation_id=request.operationId,
                provider_payment_id=str(request.providerPaymentId),
                result=request.result,
                message=getattr(request, 'message', None),
            )
            if changed:
                logger.info(
                    'receipt_processed',
                    operation_id=request.operationId,
                    provider_payment_id=str(request.providerPaymentId),
                    result=request.result,
                )
            else:
                logger.info(
                    'receipt_ignored',
                    operation_id=request.operationId,
                    provider_payment_id=str(request.providerPaymentId),
                    result=request.result,
                )
            return operation, status.HTTP_204_NO_CONTENT
        except ValueError:
            logger.error('receipt_operation_not_found',
                         operation_id=request.operationId)
            raise
        except RuntimeError as exc:
            logger.warning('receipt_conflict',
                           operation_id=request.operationId, error=str(exc))
            raise
