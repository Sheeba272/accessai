"""
Scan API routes — updated with multi-screenshot support
"""
import logging
from pathlib import Path
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse

from backend.models.schemas import (
    ScanRequest, ScanStartResponse, ScanStatusResponse
)
from backend.services.scan_service import scan_service
from backend.utils.validators import validate_url, sanitize_url
from backend.utils.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/start", response_model=ScanStartResponse)
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    url = sanitize_url(str(request.url))
    valid, err = validate_url(url)
    if not valid:
        raise HTTPException(status_code=400, detail=err)

    scan_id = await scan_service.create_scan(
        url=url, model=request.model,
        depth=request.depth, wcag_level=request.wcag_level.value,
    )
    background_tasks.add_task(
        scan_service.run_scan_background,
        scan_id=scan_id, url=url, model=request.model,
        depth=request.depth, wcag_level=request.wcag_level.value,
    )
    logger.info(f"Started scan {scan_id} for {url}")
    return ScanStartResponse(scan_id=scan_id, message="Scan started")


@router.get("/{scan_id}/status", response_model=ScanStatusResponse)
async def get_scan_status(scan_id: str):
    status = await scan_service.get_status(scan_id)
    if status.get("status") == "not_found":
        raise HTTPException(status_code=404, detail=f"Scan {scan_id} not found")
    return ScanStatusResponse(
        scan_id=scan_id, status=status["status"],
        step=status.get("step", ""), message=status.get("message", ""),
        progress=status.get("progress", 0), error=status.get("error"),
    )


@router.get("/{scan_id}/results")
async def get_scan_results(scan_id: str):
    try:
        results = await scan_service.get_results(scan_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    if results["status"] not in ("completed", "failed"):
        raise HTTPException(status_code=202, detail="Scan still in progress")
    results["scan_id"] = scan_id
    return results


@router.get("/{scan_id}/screenshot")
async def get_screenshot(scan_id: str):
    """Primary screenshot — page 1"""
    path = Path(settings.SCREENSHOTS_DIR) / f"{scan_id}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Screenshot not available")
    return FileResponse(str(path), media_type="image/png")


@router.get("/{scan_id}/screenshot/{page_num}")
async def get_screenshot_page(scan_id: str, page_num: int):
    """Additional page screenshots for multi-page scans"""
    path = Path(settings.SCREENSHOTS_DIR) / f"{scan_id}_p{page_num}.png"
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Screenshot for page {page_num} not available")
    return FileResponse(str(path), media_type="image/png")


@router.get("s/history")
async def get_history():
    scans = await scan_service.get_history()
    return {"scans": scans}
