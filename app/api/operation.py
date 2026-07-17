from fastapi import APIRouter, HTTPException, status, Response
from sqlalchemy.exc import IntegrityError
import structlog
from typing import List

from app.models import CreateOperationRequest, OperationResponse, EventResponse
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


@router.post('/{id}/submit', response_model=OperationResponse)
async def submit_operation(id: str, response: Response) -> OperationResponse:
    """
    Отправка операции провайдеру.
    """
    try:
        operation, status_code = await OperationService.submit_operation(id)
        response.status_code = status_code

        return OperationResponse(
            OperationId=operation.id,
            amount=str(operation.amount),
            currency=operation.currency,
            description=operation.description,
            status=operation.status,
            providerPaymentId=operation.provider_payment_id,
        )

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Operation with id {id} not found"
        )


@router.get('/{id}/events', response_model=List[EventResponse])
async def get_conversion_history(id: str) -> List[EventResponse]:
    """
    Получение всех событий операции, отсортированных по event_id
    """
    try:
        events = await OperationService.get_conversion_history(id)

        return [
            EventResponse(
                eventId=event.event_id,
                eventType=event.event_type,
                fromStatus=event.from_status,
                toStatus=event.to_status,
                message=event.message,
                occurredAt=event.occurred_at,
            )
            for event in events
        ]
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Event with operation id {id} not found"
        )
