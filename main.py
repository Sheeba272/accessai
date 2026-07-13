import sys
import asyncio
import os

# MUST be set before any uvicorn/fastapi imports on Windows
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse

from backend.api.routes import scan, report, health, features
from backend.utils.database import init_db
from backend.utils.logger import setup_logger

setup_logger()
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting AccessAI backend...")
    await init_db()
    yield
    logger.info("Shutting down AccessAI backend.")


app = FastAPI(
    title="AccessAI — Accessibility Testing Agent",
    description="Enterprise AI-powered WCAG 2.1 accessibility scanner",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def log_requests(request, call_next):
    logger.info(f"→ {request.method} {request.url.path}")
    response = await call_next(request)
    logger.info(f"← {response.status_code} {request.url.path}")
    return response

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(status_code=500, content={"detail": "Internal server error"})

app.include_router(health.router, tags=["health"])
app.include_router(scan.router,   prefix="/api/scan",   tags=["scan"])
app.include_router(report.router, prefix="/api/report", tags=["report"])
app.include_router(features.router, prefix="/api", tags=["features"])


os.makedirs("data/screenshots", exist_ok=True)
os.makedirs("data/reports", exist_ok=True)
app.mount("/data", StaticFiles(directory="data"), name="data")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        loop="asyncio",   # force asyncio loop (Proactor policy already set above)
    )
