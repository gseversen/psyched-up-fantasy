from fastapi import FastAPI
from contextlib import asynccontextmanager
from typing import AsyncGenerator


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup: initialize DB pool, Redis connection, etc.
    yield
    # Shutdown: close connections


app = FastAPI(
    title="Psyched Up Fantasy Swimming",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "ok"}
