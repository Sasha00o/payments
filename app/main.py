from fastapi import FastAPI
from fastapi_versioning import VersionedFastAPI
from app.core.logger import configure_logging, get_logger


app = FastAPI()

configure_logging(log_level="INFO", json_logs=False)

logger = get_logger(__name__)
logger.info("application_started", version="1.0.0")

app = VersionedFastAPI(
    app,
    version_format="{major}",
    prefix_format="/api/v{major}",
)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=80)
