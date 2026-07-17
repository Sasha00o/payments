from fastapi import APIRouter, HTTPException, Response, status

from app.models import ReceiptRequest
from app.services.operation import OperationService


router = APIRouter(tags=['Receipts'])


@router.post('/receipts', status_code=status.HTTP_204_NO_CONTENT)
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
