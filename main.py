from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from database import engine
from routers.applications import router as applications_router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(title="Job Application Tracker", lifespan=lifespan)
app.include_router(applications_router)


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
