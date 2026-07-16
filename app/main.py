from fastapi import FastAPI
from app.core.logger import configure_logging, get_logger
from app.api.operation import router as operation_router

app = FastAPI()

configure_logging()

logger = get_logger(__name__)
logger.info("application_started", version="1.0.0")

app.include_router(operation_router, prefix="/api/v1")


@app.get('/health')
async def health():
    logger.info('health_check_call', version='1.0.0')
    return {"status": "ok", "service": "payments", "version": "1.0.0"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)
