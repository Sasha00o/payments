from __future__ import annotations

import httpx
import structlog
from fastapi import status

from app.core.config import settings
from app.core.retry import compute_retry_delay
from app.models import Operation, SubmitIntent
from app.repositories import OperationRepository

logger = structlog.get_logger()


class ProviderService:
    """Сервис для взаимодействия с внешним провайдером платежей."""

    @staticmethod
    async def submit(operation: Operation, intent: SubmitIntent) -> None:
        payload = {
            'operationId': operation.id,
            'amount': str(operation.amount),
            'currency': operation.currency,
        }
        headers = {
            'Content-Type': 'application/json',
            'Idempotency-Key': operation.id,
            'X-Correlation-ID': operation.id,
        }
        url = f"{settings.PROVIDER_URL.rstrip('/')}/payments"

        try:
            async with httpx.AsyncClient(timeout=settings.PROVIDER_TIMEOUT_SECONDS) as client:
                logger.info(
                    "provider_submit_started",
                    operation_id=operation.id,
                    attempt=intent.attempt_count,
                )
                response = await client.post(url, json=payload, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning(
                "provider_submit_retry",
                operation_id=operation.id,
                attempt=intent.attempt_count,
                error=str(exc),
            )
            await OperationRepository.mark_submit_retry(
                intent.id,
                retry_delay_seconds=compute_retry_delay(intent.attempt_count),
            )
            return

        if response.status_code in {status.HTTP_200_OK, status.HTTP_202_ACCEPTED}:
            try:
                body = response.json()
            except ValueError:
                body = {}

            provider_payment_id = body.get(
                'providerPaymentId') if isinstance(body, dict) else None
            await OperationRepository.mark_submit_success(intent.id, provider_payment_id)
            logger.info(
                "provider_submit_success",
                operation_id=operation.id,
                provider_payment_id=provider_payment_id,
                status_code=response.status_code,
            )
            return

        if response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            logger.warning(
                "provider_submit_retry",
                operation_id=operation.id,
                attempt=intent.attempt_count,
                status_code=response.status_code,
            )
            await OperationRepository.mark_submit_retry(
                intent.id,
                retry_delay_seconds=compute_retry_delay(intent.attempt_count),
            )
            return
        logger.warning(
            "provider_submit_retry",
            operation_id=operation.id,
            attempt=intent.attempt_count,
            status_code=response.status_code,
        )
        await OperationRepository.mark_submit_retry(
            intent.id,
            retry_delay_seconds=compute_retry_delay(intent.attempt_count),
        )
