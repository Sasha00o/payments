from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.constants import CallbackResult, EventType, OperationStatus


class CreateOperationRequest(BaseModel):
    operationId: str = Field(...,
                             description="Уникальный идентификатор операции")
    amount: str = Field(..., pattern=r"^\d+\.\d{1,2}$",
                        description="Сумма в формате 0.00")
    currency: str = Field(..., pattern="^RUB$",
                          description="Валюта (только RUB)")
    description: Optional[str] = Field(None, description="Описание операции")

    @field_validator("amount")
    @classmethod
    def validate_amount(cls, v: str) -> str:
        try:
            amount_decimal = Decimal(v)
            if amount_decimal <= 0:
                raise ValueError("Amount must be positive")
        except Exception as e:
            raise ValueError(f"Invalid amount format: {e}")
        return v


class OperationResponse(BaseModel):
    OperationId: str
    amount: str
    currency: str
    description: Optional[str]
    status: OperationStatus
    providerPaymentId: Optional[UUID] = None

    model_config = {"from_attributes": True}


class ReceiptRequest(BaseModel):
    providerPaymentId: UUID = Field(..., description="ID платежа у провайдера")
    operationId: str = Field(..., description="ID операции")
    result: CallbackResult = Field(..., description="Результат платежа")


class EventResponse(BaseModel):
    eventId: int
    eventType: EventType
    fromStatus: Optional[OperationStatus]
    toStatus: OperationStatus
    message: Optional[str]
    occurredAt: datetime

    model_config = {"from_attributes": True}


class ProviderPaymentRequest(BaseModel):
    operationId: str
    amount: str
    currency: str


class ProviderPaymentResponse(BaseModel):
    providerPaymentId: UUID
    operationId: str
