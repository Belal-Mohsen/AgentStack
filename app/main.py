import uvicorn
from fastapi import FastAPI

from app.core.config.logging import configure_logging, get_logger
from app.core.config.settings import settings

configure_logging()
logger = get_logger(__name__)

# FastAPI app — uvicorn runs this via app.main:app
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    debug=settings.DEBUG,
)


@app.get("/health")
def health():
    return {"status": "ok"}


def main():
    logger.info("AgentStack started")
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
    )


if __name__ == "__main__":
    main()
