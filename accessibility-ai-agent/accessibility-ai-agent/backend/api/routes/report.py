"""
Report routes + HTML report generator
GET /api/report/{scan_id}?format=html|json|pdf|docx&type=scan|vpat|acr
"""
import json
import logging
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import FileResponse, JSONResponse

from backend.services.scan_service import scan_service
from backend.utils.config import settings
from backend.reports.vpat_generator import VpatAcrGenerator

router = APIRouter()
logger = logging.getLogger(__name__)


@router.get("/{scan_id}")
async def download_report(
    scan_id: str,
    format: str = Query("html", enum=["html", "json", "pdf", "docx"]),
    type: str = Query("scan", enum=["scan", "vpat", "acr"]),
    company_name: str = Query("AccessAI"),
    logo_url: str = Query(""),
):
    """Generate and return accessibility report"""
    try:
        results = await scan_service.get_results(scan_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Scan not found")

    if results["status"] != "completed":
        raise HTTPException(status_code=400, detail="Scan not yet completed")

    Path(settings.REPORTS_DIR).mkdir(parents=True, exist_ok=True)

    if type in {"vpat", "acr"}:
        generator = VpatAcrGenerator()
        previous = await _previous_completed_scan(scan_id)
        model = generator.build_model(results, previous=previous)
        model["report_type"] = "VPAT" if type == "vpat" else "Accessibility Conformance Report"
        branding = {"company_name": company_name, "logo_url": logo_url}
        stem = f"{type}-{scan_id}"
        if format == "json":
            report_path = Path(settings.REPORTS_DIR) / f"{stem}.json"
            generator.write_json(model, report_path)
            return FileResponse(str(report_path), media_type="application/json", filename=f"{stem}.json")
        if format == "docx":
            report_path = Path(settings.REPORTS_DIR) / f"{stem}.docx"
            generator.write_docx(model, report_path, branding=branding)
            return FileResponse(str(report_path), media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document", filename=f"{stem}.docx")
        if format == "pdf":
            report_path = Path(settings.REPORTS_DIR) / f"{stem}.pdf"
            generator.write_pdf(model, report_path, branding=branding)
            return FileResponse(str(report_path), media_type="application/pdf", filename=f"{stem}.pdf")
        report_path = Path(settings.REPORTS_DIR) / f"{stem}.html"
        generator.write_html(model, report_path, branding=branding)
        return FileResponse(str(report_path), media_type="text/html", filename=f"{stem}.html")

    if format == "json":
        report_path = Path(settings.REPORTS_DIR) / f"report-{scan_id}.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2)
        return FileResponse(str(report_path), media_type="application/json",
                            filename=f"accessibility-report-{scan_id}.json")

    # HTML report
    report_path = Path(settings.REPORTS_DIR) / f"report-{scan_id}.html"
    html = generate_html_report(results)
    with open(report_path, "w", encoding="utf-8") as f:
        f.write(html)
    return FileResponse(str(report_path), media_type="text/html",
                        filename=f"accessibility-report-{scan_id}.html")


async def _previous_completed_scan(scan_id: str) -> dict | None:
    history = await scan_service.get_history(limit=50)
    candidates = [scan for scan in history if scan["id"] != scan_id and scan.get("status") == "completed"]
    if not candidates:
        return None
    try:
        return await scan_service.get_results(candidates[0]["id"])
    except Exception:
        return None


def generate_html_report(data: dict) -> str:
    violations   = data.get("violations", [])
    ai_analyses  = data.get("ai_analyses", [])
    exec_summary = data.get("executive_summary", {})
    metrics      = data.get("metrics", {})
    rule_results = data.get("rule_results", {})
    scenarios    = data.get("generated_scenarios", [])
    score        = data.get("score", 0)
    url          = data.get("url", "")
    scan_id      = data.get("id", "")
    created_at   = data.get("created_at", "")

    def badge(sev):
        colors = {"critical": "#ff7b72", "high": "#ffa657", "medium": "#e3b341", "low": "#7ee787"}
        c = colors.get(sev, "#8b949e")
        return f'<span style="background:{c}22;color:{c};border:1px solid {c};border-radius:12px;padding:2px 9px;font-size:11px;font-weight:700;text-transform:uppercase">{sev}</span>'

    violations_rows = "".join([
        f"""<tr>
          <td style="padding:10px 14px">{badge(v.get('severity','low'))}</td>
          <td style="padding:10px 14px"><b>{v.get('description','')}</b><br><span style="color:#8b949e;font-size:12px">{v.get('help','')}</span></td>
          <td style="padding:10px 14px;font-family:monospace;font-size:12px">{v.get('wcag_reference','—')}</td>
          <td style="padding:10px 14px">{len(v.get('nodes',[])) or 1}</td>
        </tr>"""
        for v in violations
    ])

    ai_cards = ""
    for a in ai_analyses:
        code = f'<pre style="background:#0d1117;color:#7ee787;padding:12px;border-radius:8px;overflow-x:auto;font-size:12px">{a.get("sample_code_fix","")}</pre>' if a.get("sample_code_fix") else ""
        ai_cards += f"""
        <div style="background:#161b22;border:1px solid #30363d;border-radius:12px;padding:18px;margin-bottom:14px">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
            <b style="font-size:15px">{a.get('issue_title','')}</b>
            {badge(a.get('severity','low'))}
          </div>
          <p><b>Business impact:</b> {a.get('business_impact','')}</p>
          <p><b>Affected users:</b> {a.get('affected_users','')}</p>
          <p><b>Recommended fix:</b> {a.get('recommended_fix','')}</p>
          {code}
        </div>"""

    rule_rows = "".join([
        f"""<tr>
          <td style="padding:10px 14px">{badge(r.get('severity','low'))}</td>
          <td style="padding:10px 14px"><b>{r.get('name','')}</b><br><span style="color:#8b949e;font-size:12px">{r.get('message','')}</span></td>
          <td style="padding:10px 14px">{r.get('status','')}</td>
          <td style="padding:10px 14px">{'; '.join(r.get('evidence', [])[:2])}</td>
        </tr>"""
        for r in rule_results.get("results", [])
    ])

    scenario_rows = "".join([
        f"""<tr>
          <td style="padding:10px 14px;font-family:monospace">{s.get('test_case_id','')}</td>
          <td style="padding:10px 14px">{s.get('category','')}</td>
          <td style="padding:10px 14px"><b>{s.get('scenario_description','')}</b><br><span style="color:#8b949e;font-size:12px">{s.get('expected_result','')}</span></td>
          <td style="padding:10px 14px">{', '.join(s.get('wcag_mapping', []))}</td>
          <td style="padding:10px 14px">{s.get('automation_feasibility','')}</td>
        </tr>"""
        for s in scenarios
    ])

    recs_html = "".join([
        f'<li style="margin-bottom:8px">{r}</li>'
        for r in exec_summary.get("recommendations", [])
    ])

    score_color = "#7ee787" if score >= 75 else ("#ffa657" if score >= 50 else "#ff7b72")

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Accessibility Report — {url}</title>
<style>
  body {{ margin:0; font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;
    background:#0d1117; color:#f0f6fc; line-height:1.6; }}
  .container {{ max-width:900px; margin:0 auto; padding:32px 24px; }}
  h1 {{ font-size:26px; font-weight:700; margin-bottom:4px; }}
  h2 {{ font-size:18px; font-weight:600; border-bottom:1px solid #30363d; padding-bottom:8px; margin:28px 0 14px; }}
  table {{ width:100%; border-collapse:collapse; }}
  th {{ text-align:left; padding:8px 14px; color:#8b949e; font-size:11px; text-transform:uppercase;
    letter-spacing:.5px; border-bottom:1px solid #30363d; background:#161b22; }}
  tr:hover td {{ background:#161b22; }}
  .metric {{ display:inline-block; background:#161b22; border:1px solid #30363d;
    border-radius:10px; padding:14px 20px; text-align:center; margin:4px; min-width:90px; }}
  .metric-val {{ font-size:26px; font-weight:700; line-height:1; }}
  .metric-lbl {{ font-size:11px; color:#8b949e; text-transform:uppercase; letter-spacing:.5px; }}
  a {{ color:#58a6ff; }}
  .tag {{ background:#21262d; border:1px solid #30363d; border-radius:6px;
    padding:2px 8px; font-size:11px; color:#8b949e; font-family:monospace; }}
</style>
</head>
<body>
<div class="container">
  <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:24px">
    <div>
      <h1>♿ Accessibility Report</h1>
      <div style="color:#8b949e;font-size:14px">
        <a href="{url}">{url}</a> &bull; Scan ID: {scan_id} &bull; {created_at[:10] if created_at else ''}
      </div>
    </div>
    <div style="text-align:center">
      <div style="font-size:48px;font-weight:800;color:{score_color}">{int(score)}</div>
      <div style="font-size:12px;color:#8b949e">/ 100</div>
    </div>
  </div>

  <!-- METRICS -->
  <h2>Scan Summary</h2>
  <div>
    <div class="metric"><div class="metric-val" style="color:#ff7b72">{metrics.get('critical',0)}</div><div class="metric-lbl">Critical</div></div>
    <div class="metric"><div class="metric-val" style="color:#ffa657">{metrics.get('high',0)}</div><div class="metric-lbl">High</div></div>
    <div class="metric"><div class="metric-val" style="color:#e3b341">{metrics.get('medium',0)}</div><div class="metric-lbl">Medium</div></div>
    <div class="metric"><div class="metric-val" style="color:#7ee787">{metrics.get('low',0)}</div><div class="metric-lbl">Low</div></div>
    <div class="metric"><div class="metric-val" style="color:#58a6ff">{metrics.get('passed',0)}</div><div class="metric-lbl">Passed</div></div>
  </div>

  <!-- EXECUTIVE SUMMARY -->
  <h2>Executive Summary</h2>
  <p>{exec_summary.get('overview','')}</p>
  <p>{exec_summary.get('key_findings','')}</p>
  <h3 style="font-size:15px;margin:16px 0 8px">Priority Recommendations</h3>
  <ol style="color:#c9d1d9;padding-left:20px">{recs_html}</ol>
  <p><b>Compliance status:</b> {exec_summary.get('compliance_status','')}</p>

  <!-- VIOLATIONS TABLE -->
  <h2>Violations ({len(violations)})</h2>
  <table>
    <thead><tr><th>Severity</th><th>Issue</th><th>WCAG</th><th>Elements</th></tr></thead>
    <tbody>{violations_rows}</tbody>
  </table>

  <!-- AI ANALYSIS -->
  <h2>AI-Generated Remediation Guide</h2>
  {ai_cards}

  <!-- RULE ENGINE -->
  <h2>Additional Guideline Validation</h2>
  <p>Rule engine summary: {rule_results.get('summary', {}).get('passed', 0)} passed,
     {rule_results.get('summary', {}).get('failed', 0)} failed,
     {rule_results.get('summary', {}).get('manual_review', 0)} require review.</p>
  <table>
    <thead><tr><th>Severity</th><th>Rule</th><th>Status</th><th>Evidence</th></tr></thead>
    <tbody>{rule_rows}</tbody>
  </table>

  <!-- GENERATED SCENARIOS -->
  <h2>AI-Generated Accessibility Test Scenarios</h2>
  <table>
    <thead><tr><th>ID</th><th>Category</th><th>Scenario</th><th>WCAG</th><th>Automation</th></tr></thead>
    <tbody>{scenario_rows}</tbody>
  </table>

  <hr style="border:none;border-top:1px solid #30363d;margin:32px 0">
  <p style="color:#8b949e;font-size:12px;text-align:center">
    Generated by AccessAI &bull; Powered by Ollama local LLMs &bull; WCAG 2.1 AA
  </p>
</div>
</body>
</html>"""
