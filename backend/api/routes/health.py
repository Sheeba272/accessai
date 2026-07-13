"""Health and Ollama status endpoints"""
from fastapi import APIRouter
import httpx
from backend.utils.config import settings

router = APIRouter()


@router.get("/health")
async def health():
    return {"status": "ok", "app": settings.APP_NAME, "version": "1.0.0"}


@router.get("/health/ollama")
async def ollama_health():
    try:
        async with httpx.AsyncClient(timeout=3) as client:
            r = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            if r.status_code == 200:
                models = [m["name"] for m in r.json().get("models", [])]
                return {"status": "online", "models": models}
    except Exception:
        pass
    return {"status": "offline", "models": [], "hint": "Run: ollama serve"}
