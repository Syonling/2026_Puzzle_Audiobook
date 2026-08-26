import logging, uvicorn
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.core.config import STATIC_DIR, settings
from app.db.database import init_db
from app.core.logging_config import setup_logging
from app.routers import (
    system,
    auth,
    stories,
    ai_questions,
    project,
    assets,
    logs,
)


setup_logging()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    logger.info("Database ready, application starting")

    yield

    logger.info("Application shutting down")


app = FastAPI(
    title=settings.app_name,
    lifespan=lifespan,
)


app.include_router(system.router)
app.include_router(auth.router)
app.include_router(stories.router)
app.include_router(ai_questions.router)
app.include_router(project.router)
app.include_router(assets.router)
app.include_router(logs.router)

app.mount(
    "/static",
    StaticFiles(directory=STATIC_DIR),
    name="static",
)


@app.get("/", include_in_schema=False)
def index():
    return FileResponse(STATIC_DIR / "index.html")


if __name__ == "__main__":
    logger.info("Start puzzle audiobook system")
    uvicorn.run("app.main:app",host='127.0.0.1', port=1234, reload=True)
