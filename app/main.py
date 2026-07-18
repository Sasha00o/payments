import asyncio

from fastapi import FastAPI
from app.api.receipts import router as receipt_router
from app.api.operation import router as operation_router
from app.core.logger import configure_logging, get_logger
from app.services.operation import run_submission_worker, run_metrics_worker
from app.core.config import settings
from prometheus_client import make_asgi_app

app = FastAPI()

metrics_app = make_asgi_app()
app.mount("/metrics", metrics_app)

configure_logging(
    log_level=settings.LOG_LEVEL,
    json_logs=settings.LOG_JSON)

logger = get_logger(__name__)
logger.info('application_started', version='1.0.0')

app.include_router(operation_router)
app.include_router(receipt_router)


@app.get('/health')
async def health():
    logger.info('health_check_call', version='1.0.0')
    return {'status': 'ok', 'service': 'payments', 'version': '1.0.0'}


@app.on_event('startup')
async def startup_event() -> None:
    asyncio.create_task(run_submission_worker())
    asyncio.create_task(run_metrics_worker())


if __name__ == '__main__':
    import uvicorn
    uvicorn.run(app, host='0.0.0.0', port=8080)
