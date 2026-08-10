from contextlib import asynccontextmanager
from typing import AsyncGenerator, Literal

from fastapi import Depends, FastAPI, Response, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from backend.config import get_settings
from backend.db.session import dispose_engine, get_session, init_engine


class HealthResponse(BaseModel):
    status: Literal["ok", "unhealthy"]
    database: Literal["connected", "disconnected"]


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    init_engine(settings)
    yield
    await dispose_engine()


app = FastAPI(
    title="Psyched Up Fantasy Swimming",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health", response_model=HealthResponse)
async def health_check(
    response: Response,
    session: AsyncSession = Depends(get_session),
) -> HealthResponse:
    try:
        await session.execute(text("SELECT 1"))
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return HealthResponse(status="unhealthy", database="disconnected")

    return HealthResponse(status="ok", database="connected")
