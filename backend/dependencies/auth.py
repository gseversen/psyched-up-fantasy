from fastapi import Header, HTTPException, status

from backend.config import get_settings


async def verify_ingestion_api_key(
    x_api_key: str = Header(..., alias="X-API-Key"),
) -> str:
    settings = get_settings()
    if x_api_key != settings.ingestion_api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing API key",
        )
    return x_api_key
