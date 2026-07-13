"""VPAT and ACR report generation utilities."""
import html
import json
import textwrap
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any


WCAG_CRITERIA = [
    ("1.1.1", "Non-text Content"),
    ("1.2.1", "Audio-only and Video-only"),
    ("1.2.2", "Captions"),
    ("1.2.3", "Audio Description or Media Alternative"),
    ("1.3.1", "Info and Relationships"),
    ("1.3.2", "Meaningful Sequence"),
    ("1.3.3", "Sensory Characteristics"),
    ("1.4.1", "Use of Color"),
    ("1.4.3", "Contrast Minimum"),
    ("1.4.4", "Resize Text"),
    ("1.4.5", "Images of Text"),
    ("1.4.10", "Reflow"),
    ("1.4.11", "Non-text Contrast"),
    ("1.4.12", "Text Spacing"),
    ("1.4.13", "Content on Hover or Focus"),
    ("2.1.1", "Keyboard"),
    ("2.1.2", "No Keyboard Trap"),
    ("2.1.4", "Character Key Shortcuts"),
    ("2.2.1", "Timing Adjustable"),
    ("2.2.2", "Pause, Stop, Hide"),
    ("2.3.1", "Three Flashes or Below Threshold"),
    ("2.4.1", "Bypass Blocks"),
    ("2.4.2", "Page Titled"),
    ("2.4.3", "Focus Order"),
    ("2.4.4", "Link Purpose"),
    ("2.4.5", "Multiple Ways"),
    ("2.4.6", "Headings and Labels"),
    ("2.4.7", "Focus Visible"),
    ("2.5.1", "Pointer Gestures"),
    ("2.5.2", "Pointer Cancellation"),
    ("2.5.3", "Label in Name"),
    ("2.5.4", "Motion Actuation"),
    ("3.1.1", "Language of Page"),
    ("3.1.2", "Language of Parts"),
    ("3.2.1", "On Focus"),
    ("3.2.2", "On Input"),
    ("3.2.3", "Consistent Navigation"),
    ("3.2.4", "Consistent Identification"),
    ("3.3.1", "Error Identification"),
    ("3.3.2", "Labels or Instructions"),
    ("3.3.3", "Error Suggestion"),
    ("3.3.4", "Error Prevention"),
    ("4.1.1", "Parsing"),
    ("4.1.2", "Name, Role, Value"),
    ("4.1.3", "Status Messages"),
]


class VpatAcrGenerator:
    def build_model(self, data: dict[str, Any], previous: dict[str, Any] | None = None) -> dict[str, Any]:
        violations = data.get("violations", [])
        rule_results = data.get("rule_results", {})
        scenarios = data.get("generated_scenarios", [])
        metrics = data.get("metrics", {})
        score = float(data.get("score") or 0)

        criteria = []
        for criterion_id, name in WCAG_CRITERIA:
            defects = self._matching_defects(criterion_id, violations, rule_results.get("results", []))
            status = "Supports" if not defects else ("Partially Supports" if len(defects) <= 2 else "Does Not Support")
            criteria.append({
                "criterion": f"WCAG 2.1 SC {criterion_id}",
                "name": name,
                "conformance_level": "AA",
                "status": status,
                "remarks": self._remarks(defects),
                "defects": defects,
            })

        failed_criteria = sum(1 for row in criteria if row["status"] != "Supports")
        compliance_percentage = round(((len(criteria) - failed_criteria) / len(criteria)) * 100, 1)
        severity_summary = {
            "critical": metrics.get("critical", 0),
            "high": metrics.get("high", 0),
            "medium": metrics.get("medium", 0),
            "low": metrics.get("low", 0),
            "custom_rule_failures": rule_results.get("summary", {}).get("failed", 0),
        }
        current = {
            "report_type": "VPAT 2.5 / Accessibility Conformance Report",
            "product": data.get("url", ""),
            "scan_id": data.get("id") or data.get("scan_id", ""),
            "generated_at": datetime.utcnow().isoformat(),
            "standard": "WCAG 2.1 Level AA",
            "accessibility_score": score,
            "compliance_percentage": compliance_percentage,
            "severity_summary": severity_summary,
            "executive_summary": data.get("executive_summary", {}),
            "wcag_criteria": criteria,
            "defects": self._defects(violations, rule_results),
            "remediation_recommendations": self._recommendations(data),
            "generated_scenarios": scenarios,
            "evidence": {
                "screenshot": f"/api/scan/{data.get('id') or data.get('scan_id')}/screenshot",
                "rule_results": rule_results,
            },
            "trend_analysis": self._trend(current_score=score, previous=previous),
        }
        return current

    def write_json(self, model: dict[str, Any], path: Path) -> None:
        path.write_text(json.dumps(model, indent=2), encoding="utf-8")

    def write_html(self, model: dict[str, Any], path: Path, branding: dict[str, str] | None = None) -> None:
        branding = branding or {}
        rows = "\n".join(
            f"<tr><td>{html.escape(c['criterion'])}</td><td>{html.escape(c['name'])}</td><td>{html.escape(c['status'])}</td><td>{html.escape(c['remarks'])}</td></tr>"
            for c in model["wcag_criteria"]
        )
        defects = "\n".join(
            f"<li><strong>{html.escape(d['severity'].upper())}</strong> {html.escape(d['title'])}<br><span>{html.escape(d['recommendation'])}</span></li>"
            for d in model["defects"][:30]
        ) or "<li>No defects identified.</li>"
        scenarios = "\n".join(
            f"<tr><td>{html.escape(s['test_case_id'])}</td><td>{html.escape(s['category'])}</td><td>{html.escape(s['scenario_description'])}</td><td>{html.escape(', '.join(s.get('wcag_mapping', [])))}</td><td>{html.escape(s['automation_feasibility'])}</td></tr>"
            for s in model.get("generated_scenarios", [])[:20]
        )
        logo = f"<img src='{html.escape(branding.get('logo_url', ''))}' alt='' class='logo'>" if branding.get("logo_url") else ""
        company = html.escape(branding.get("company_name", "AccessAI"))
        document = f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>VPAT ACR - {html.escape(model['product'])}</title>
<style>
body {{ font-family: Arial, sans-serif; color: #172033; margin: 0; }}
header {{ padding: 32px 40px; background: #0f172a; color: white; }}
.logo {{ max-height: 48px; margin-bottom: 16px; }}
main {{ padding: 32px 40px; }}
h1 {{ margin: 0 0 8px; font-size: 28px; }}
h2 {{ margin-top: 32px; border-bottom: 1px solid #d8dee9; padding-bottom: 8px; }}
.metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }}
.metric {{ border: 1px solid #d8dee9; padding: 14px; border-radius: 6px; }}
.metric strong {{ display: block; font-size: 26px; }}
table {{ border-collapse: collapse; width: 100%; margin-top: 12px; }}
th, td {{ border: 1px solid #d8dee9; padding: 8px; text-align: left; vertical-align: top; }}
th {{ background: #f1f5f9; }}
li {{ margin-bottom: 10px; }}
</style>
</head>
<body>
<header>{logo}<h1>{company} VPAT / ACR</h1><p>{html.escape(model['product'])}</p><p>Generated {html.escape(model['generated_at'][:10])}</p></header>
<main>
<section class="metrics">
<div class="metric"><strong>{model['accessibility_score']}</strong>Accessibility score</div>
<div class="metric"><strong>{model['compliance_percentage']}%</strong>Compliance</div>
<div class="metric"><strong>{model['severity_summary']['critical']}</strong>Critical</div>
<div class="metric"><strong>{model['severity_summary']['high']}</strong>High</div>
</section>
<h2>Executive Summary</h2>
<p>{html.escape(model.get('executive_summary', {}).get('overview', ''))}</p>
<p>{html.escape(model.get('executive_summary', {}).get('compliance_status', ''))}</p>
<h2>WCAG Criteria Mapping</h2>
<table><thead><tr><th>Criterion</th><th>Name</th><th>Status</th><th>Remarks and Evidence</th></tr></thead><tbody>{rows}</tbody></table>
<h2>Identified Defects and Remediation</h2>
<ul>{defects}</ul>
<h2>AI-Generated Accessibility Scenarios</h2>
<table><thead><tr><th>ID</th><th>Category</th><th>Scenario</th><th>WCAG</th><th>Automation</th></tr></thead><tbody>{scenarios}</tbody></table>
<h2>Historical Comparison and Trend</h2>
<p>{html.escape(model['trend_analysis']['summary'])}</p>
</main>
</body>
</html>"""
        path.write_text(document, encoding="utf-8")

    def write_docx(self, model: dict[str, Any], path: Path, branding: dict[str, str] | None = None) -> None:
        lines = self._plain_lines(model, branding)
        body = "".join(f"<w:p><w:r><w:t>{html.escape(line)}</w:t></w:r></w:p>" for line in lines)
        document_xml = f"""<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>{body}</w:body></w:document>"""
        content_types = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>"""
        rels = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>"""
        with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as docx:
            docx.writestr("[Content_Types].xml", content_types)
            docx.writestr("_rels/.rels", rels)
            docx.writestr("word/document.xml", document_xml)

    def write_pdf(self, model: dict[str, Any], path: Path, branding: dict[str, str] | None = None) -> None:
        # Minimal text PDF writer to keep export dependency-free.
        lines = []
        for line in self._plain_lines(model, branding):
            lines.extend(textwrap.wrap(line, 92) or [""])
        pages = [lines[i:i + 44] for i in range(0, len(lines), 44)] or [[]]
        objects = ["<< /Type /Catalog /Pages 2 0 R >>"]
        kids = []
        for index, page_lines in enumerate(pages):
            page_obj = 3 + index * 2
            content_obj = page_obj + 1
            kids.append(f"{page_obj} 0 R")
            objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Resources << /Font << /F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> >> >> /Contents {content_obj} 0 R >>")
            stream = "BT /F1 10 Tf 40 760 Td 14 TL " + "".join(f"({self._pdf_escape(line)}) Tj T* " for line in page_lines) + "ET"
            objects.append(f"<< /Length {len(stream.encode('latin-1', 'ignore'))} >>\nstream\n{stream}\nendstream")
        objects.insert(1, f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>")
        content = "%PDF-1.4\n"
        offsets = [0]
        for idx, obj in enumerate(objects, start=1):
            offsets.append(len(content.encode("latin-1", "ignore")))
            content += f"{idx} 0 obj\n{obj}\nendobj\n"
        xref = len(content.encode("latin-1", "ignore"))
        content += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n"
        content += "".join(f"{offset:010d} 00000 n \n" for offset in offsets[1:])
        content += f"trailer << /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF"
        path.write_bytes(content.encode("latin-1", "ignore"))

    def _plain_lines(self, model: dict[str, Any], branding: dict[str, str] | None = None) -> list[str]:
        company = (branding or {}).get("company_name", "AccessAI")
        lines = [
            f"{company} VPAT / Accessibility Conformance Report",
            f"Product: {model['product']}",
            f"Standard: {model['standard']}",
            f"Generated: {model['generated_at']}",
            f"Accessibility score: {model['accessibility_score']}",
            f"Compliance percentage: {model['compliance_percentage']}%",
            "",
            "Executive Summary",
            model.get("executive_summary", {}).get("overview", ""),
            model.get("executive_summary", {}).get("compliance_status", ""),
            "",
            "Severity Summary",
        ]
        lines.extend(f"{k}: {v}" for k, v in model["severity_summary"].items())
        lines.extend(["", "WCAG Criteria Mapping"])
        lines.extend(f"{c['criterion']} {c['name']} - {c['status']} - {c['remarks']}" for c in model["wcag_criteria"])
        lines.extend(["", "Defects and Recommendations"])
        lines.extend(f"{d['severity'].upper()}: {d['title']} - {d['recommendation']}" for d in model["defects"][:40])
        lines.extend(["", "Trend Analysis", model["trend_analysis"]["summary"]])
        return lines

    def _pdf_escape(self, text: str) -> str:
        return str(text).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")

    def _matching_defects(self, criterion_id: str, violations: list[dict[str, Any]], rule_results: list[dict[str, Any]]) -> list[str]:
        matches = []
        for violation in violations:
            haystack = " ".join([violation.get("wcag_reference", ""), " ".join(violation.get("tags", []))])
            compact = criterion_id.replace(".", "")
            if criterion_id in haystack or f"wcag{compact}" in haystack.lower():
                matches.append(violation.get("description") or violation.get("id"))
        for rule in rule_results:
            if criterion_id in rule.get("wcag", []) and rule.get("status") == "fail":
                matches.append(rule.get("name"))
        return matches

    def _remarks(self, defects: list[str]) -> str:
        if not defects:
            return "No failures detected in automated scan or custom rule evidence."
        return "; ".join(defects[:3])

    def _defects(self, violations: list[dict[str, Any]], rule_results: dict[str, Any]) -> list[dict[str, Any]]:
        defects = []
        for violation in violations:
            defects.append({
                "source": "axe-core",
                "title": violation.get("description") or violation.get("id"),
                "severity": violation.get("severity", "medium"),
                "wcag": violation.get("wcag_reference", "WCAG 2.1"),
                "evidence": [node.get("html", "")[:300] for node in violation.get("nodes", [])[:3]],
                "recommendation": violation.get("help", "Review and remediate according to WCAG guidance."),
            })
        for rule in rule_results.get("results", []):
            if rule.get("status") == "fail":
                defects.append({
                    "source": "rule-engine",
                    "title": rule.get("name"),
                    "severity": rule.get("severity", "medium"),
                    "wcag": ", ".join(rule.get("wcag", [])),
                    "evidence": rule.get("evidence", []),
                    "recommendation": rule.get("message", "Remediate the failed rule evidence."),
                })
        return defects

    def _recommendations(self, data: dict[str, Any]) -> list[str]:
        summary_recs = data.get("executive_summary", {}).get("recommendations", [])
        defaults = [
            "Prioritize critical and high-severity WCAG 2.1 AA failures.",
            "Add regression tests for keyboard, screen reader, contrast, form, and dialog workflows.",
            "Review custom enterprise rule failures before release sign-off.",
        ]
        return list(dict.fromkeys(summary_recs + defaults))

    def _trend(self, current_score: float, previous: dict[str, Any] | None) -> dict[str, Any]:
        if not previous:
            return {"direction": "baseline", "delta": 0, "summary": "This is the baseline report for historical comparison."}
        previous_score = float(previous.get("score") or previous.get("accessibility_score") or 0)
        delta = round(current_score - previous_score, 1)
        direction = "improved" if delta > 0 else ("declined" if delta < 0 else "unchanged")
        return {"direction": direction, "delta": delta, "summary": f"Accessibility score {direction} by {abs(delta)} points compared with the previous report."}
