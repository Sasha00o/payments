from typing import List

import structlog
from fastapi import APIRouter, HTTPException, Response, status
from sqlalchemy.exc import IntegrityError

from app.models import CreateOperationRequest, EventResponse, OperationResponse, ReceiptRequest
from app.services.operation import OperationService

logger = structlog.get_logger()
router = APIRouter(prefix='/operations', tags=['Operations'])


@router.post('', status_code=status.HTTP_201_CREATED, response_model=OperationResponse)
async def create_operation(request: CreateOperationRequest) -> OperationResponse:
    """Создать новую операцию."""
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
    except IntegrityError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f'Operation with id {request.operationId} already exists',
        ) from exc


@router.get('/{id}', response_model=OperationResponse)
async def get_operation(id: str) -> OperationResponse:
    operation = await OperationService.get_operation(id)
    if operation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail=f'Operation with id {id} not found')

    return OperationResponse(
        OperationId=operation.id,
        amount=str(operation.amount),
        currency=operation.currency,
        description=operation.description,
        status=operation.status,
        providerPaymentId=operation.provider_payment_id,
    )


@router.post('/{id}/submit', response_model=OperationResponse)
async def submit_operation(id: str, response: Response) -> OperationResponse:
    """Один раз отправить операцию провайдеру и сохранить идемпотентность."""
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
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Operation with id {id} not found',
        ) from exc


@router.get('/{id}/events', response_model=List[EventResponse])
async def get_conversion_history(id: str) -> List[EventResponse]:
    """Получить все события операции, отсортированные по event_id."""
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
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f'Event with operation id {id} not found',
        ) from exc


receipt_router = APIRouter(tags=['Receipts'])


@receipt_router.post('/receipts', status_code=status.HTTP_204_NO_CONTENT)
async def receive_receipt(request: ReceiptRequest) -> Response:
    try:
        await OperationService.handle_receipt(request)
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND,
                            detail='Operation not found') from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                            detail='Provider payment id mismatch') from exc
