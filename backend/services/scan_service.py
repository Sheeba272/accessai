"""
Scan Service — orchestrates scanner + AI + database
"""
import uuid
import json
import logging
from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from backend.utils.config import settings
from backend.utils.database import ScanRecord, AsyncSessionLocal
from backend.scanner.axe_scanner import AccessibilityScanner
from backend.ai_engine.ollama_service import AccessibilityAIService

logger = logging.getLogger(__name__)

_scan_status: dict[str, dict] = {}


class ScanService:

    async def create_scan(self, url: str, model: str, depth: int, wcag_level: str) -> str:
        scan_id = str(uuid.uuid4())[:8]
        async with AsyncSessionLocal() as db:
            record = ScanRecord(id=scan_id, url=url, model=model, status="pending", step="")
            db.add(record)
            await db.commit()
        _scan_status[scan_id] = {"scan_id": scan_id, "status": "pending", "step": "", "message": "Queued", "progress": 0}
        return scan_id

    async def run_scan_background(self, scan_id: str, url: str, model: str, depth: int, wcag_level: str):
        """Background task: full scan pipeline"""
        try:
            await self._update_status(scan_id, "scanning", "browser", "Launching browser", 5)

            async def on_step(step_name):
                step_map = {
                    "browser":    ("browser",    "Launching browser",          10),
                    "navigate":   ("navigate",   "Navigating to URL",          20),
                    "axe_inject": ("axe_inject", "Injecting axe-core",         35),
                    "scanning":   ("scanning",   "Running accessibility scan", 50),
                }
                if step_name in step_map:
                    s, msg, pct = step_map[step_name]
                    await self._update_status(scan_id, "scanning", s, msg, pct)

            screenshot_path = str(Path(settings.SCREENSHOTS_DIR) / f"{scan_id}.png")
            Path(settings.SCREENSHOTS_DIR).mkdir(parents=True, exist_ok=True)

            scanner = AccessibilityScanner(headless=settings.BROWSER_HEADLESS)
            scan_result = await scanner.scan(
                url=url,
                wcag_level=wcag_level,
                depth=depth,
                screenshot_path=screenshot_path,
                on_step=on_step,
            )

            violations         = scan_result["violations"]
            metrics            = scan_result["metrics"]
            score              = scan_result["score"]
            passed_checks      = scan_result.get("passed_checks", [])
            extra_screenshots  = scan_result.get("extra_screenshots", [])

            # AI analysis
            await self._update_status(scan_id, "scanning", "ai_analysis", "AI analyzing violations", 65)
            ai_service  = AccessibilityAIService(model=model)
            ai_analyses = await ai_service.analyze_all_violations(violations, max_ai=5)

            # Executive summary
            await self._update_status(scan_id, "scanning", "ai_analysis", "Generating executive summary", 85)
            exec_summary = await ai_service.generate_executive_summary(url, score, violations, metrics)

            # Save to DB
            await self._update_status(scan_id, "scanning", "reporting", "Saving report", 95)
            await self._save_results(
                scan_id=scan_id,
                score=score,
                violations=violations,
                ai_analyses=ai_analyses,
                exec_summary=exec_summary,
                metrics=metrics,
                passed_checks=passed_checks,
                extra_screenshots=extra_screenshots,
            )

            await self._update_status(scan_id, "completed", "completed", "Scan complete", 100)
            logger.info(f"Scan {scan_id} completed: score={score}, violations={len(violations)}, passed={len(passed_checks)}")

        except Exception as e:
            logger.error(f"Scan {scan_id} failed: {e}", exc_info=True)
            await self._update_status(scan_id, "failed", "error", str(e), 0, error=str(e))
            await self._mark_failed(scan_id, str(e))

    async def get_status(self, scan_id: str) -> dict:
        if scan_id in _scan_status:
            return _scan_status[scan_id]
        async with AsyncSessionLocal() as db:
            record = await db.get(ScanRecord, scan_id)
            if record:
                return {"scan_id": scan_id, "status": record.status, "step": record.step or "",
                        "message": record.status, "progress": 100 if record.status == "completed" else 0,
                        "error": record.error}
        return {"scan_id": scan_id, "status": "not_found", "step": "", "message": "Not found", "progress": 0}

    async def get_results(self, scan_id: str) -> dict:
        async with AsyncSessionLocal() as db:
            record = await db.get(ScanRecord, scan_id)
            if not record:
                raise ValueError(f"Scan {scan_id} not found")
            return record.to_dict()

    async def get_history(self, limit: int = 20) -> list:
        async with AsyncSessionLocal() as db:
            result = await db.execute(select(ScanRecord).order_by(ScanRecord.created_at.desc()).limit(limit))
            records = result.scalars().all()
            return [{"id": r.id, "url": r.url, "score": r.score, "status": r.status,
                     "created_at": r.created_at.isoformat() if r.created_at else ""}
                    for r in records]

    async def _update_status(self, scan_id, status, step, message, progress, error=None):
        _scan_status[scan_id] = {"scan_id": scan_id, "status": status, "step": step,
                                  "message": message, "progress": progress, "error": error}
        try:
            async with AsyncSessionLocal() as db:
                record = await db.get(ScanRecord, scan_id)
                if record:
                    record.status = status
                    record.step   = step
                    await db.commit()
        except Exception:
            pass

    async def _save_results(self, scan_id, score, violations, ai_analyses, exec_summary, metrics, passed_checks=None, extra_screenshots=None):
        async with AsyncSessionLocal() as db:
            record = await db.get(ScanRecord, scan_id)
            if record:
                record.status           = "completed"
                record.score            = score
                record.violations       = json.dumps(violations)
                record.ai_analyses      = json.dumps(ai_analyses)
                record.exec_summary     = json.dumps(exec_summary)
                record.metrics          = json.dumps(metrics)
                record.passed_checks    = json.dumps(passed_checks or [])
                record.extra_screenshots = json.dumps(extra_screenshots or [])
                record.completed_at     = datetime.utcnow()
                await db.commit()

    async def save_rule_results(self, scan_id: str, rule_results: dict):
        async with AsyncSessionLocal() as db:
            record = await db.get(ScanRecord, scan_id)
            if not record:
                raise ValueError(f"Scan {scan_id} not found")
            record.rule_results = json.dumps(rule_results or {})
            await db.commit()

    async def save_generated_scenarios(self, scan_id: str, scenarios: list):
        async with AsyncSessionLocal() as db:
            record = await db.get(ScanRecord, scan_id)
            if not record:
                raise ValueError(f"Scan {scan_id} not found")
            record.generated_scenarios = json.dumps(scenarios or [])
            await db.commit()

    async def _mark_failed(self, scan_id, error_msg):
        try:
            async with AsyncSessionLocal() as db:
                record = await db.get(ScanRecord, scan_id)
                if record:
                    record.status = "failed"
                    record.error  = error_msg
                    await db.commit()
        except Exception:
            pass


scan_service = ScanService()
