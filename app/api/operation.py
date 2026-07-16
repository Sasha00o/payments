from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError
import structlog

from app.models import CreateOperationRequest, OperationResponse
from app.services.operation import OperationService

logger = structlog.get_logger()
router = APIRouter(prefix='/operations', tags=['Operations'])


@router.post('', status_code=status.HTTP_201_CREATED, response_model=OperationResponse)
async def create_operation(request: CreateOperationRequest) -> OperationResponse:
    """
    Создание новой операции
    """
    try:
        operation = await OperationService.create_operation(request)

        return OperationResponse(
            OperationId=operation.id,
            amount=str(operation.amount),
            currency=operation.currency,
            description=operation.description,
            status=operation.status,
            providerPaymentId=operation.provider_payment_id,
        )

    except IntegrityError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Operation with id {request.operationId} already exists"
        )
