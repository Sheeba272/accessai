"""
AI Engine — Ollama integration
Prompt engineering, retry logic, JSON parsing
"""
import json
import logging
import asyncio
import re
from typing import Optional
import httpx

from backend.utils.config import settings

logger = logging.getLogger(__name__)

# =====================================================
# PROMPT TEMPLATES
# =====================================================

VIOLATION_ANALYSIS_PROMPT = """You are an expert accessibility engineer and WCAG 2.1 specialist.
Analyze the following web accessibility violation and provide a detailed, actionable response.

Violation ID: {violation_id}
Description: {description}
Help text: {help_text}
WCAG Tags: {tags}
Severity: {severity}
Failing HTML: {html_snippet}

When you write "recommended_fix" and "sample_code_fix":
- Use the failing HTML as the starting point.
- Recommend exact attribute, selector, text, ARIA, CSS, or markup changes a developer can apply.
- In "sample_code_fix", return a corrected snippet, not generic advice.
- If the original snippet is incomplete, preserve its visible text/classes and add the missing accessible markup.

Respond ONLY with a valid JSON object — no markdown, no explanation, no preamble.
Use this exact structure:
{{
  "issue_title": "Short descriptive title of the issue",
  "severity": "{severity}",
  "wcag_reference": "e.g. WCAG 2.1 SC 1.1.1 (Level AA)",
  "business_impact": "How this affects the business: legal risk, user exclusion, reputation",
  "affected_users": "Which groups of users are impacted and how",
  "technical_explanation": "Clear technical explanation of why this is a problem",
  "recommended_fix": "Step-by-step guidance for developers to fix this issue",
  "sample_code_fix": "Corrected HTML/code snippet showing the fix",
  "priority": "P1, P2, or P3 based on severity and impact"
}}"""


EXECUTIVE_SUMMARY_PROMPT = """You are a senior accessibility consultant preparing an executive summary.

Website: {url}
Accessibility Score: {score}/100
Total violations: {total}
Critical: {critical}, High: {high}, Medium: {medium}, Low: {low}
Passed checks: {passed}

Top violations:
{top_violations}

Respond ONLY with a valid JSON object:
{{
  "overview": "2-3 sentence executive overview of the accessibility status",
  "key_findings": "2-3 sentences highlighting the most important findings",
  "recommendations": [
    "Priority recommendation 1",
    "Priority recommendation 2",
    "Priority recommendation 3",
    "Priority recommendation 4",
    "Priority recommendation 5"
  ],
  "compliance_status": "Assessment of WCAG 2.1 AA compliance status",
  "score_reasoning": "Brief explanation of how the score was calculated"
}}"""


DEVELOPER_SUMMARY_PROMPT = """You are a senior developer writing a remediation guide.

Website: {url}
Violations to address: {violation_count}

Violations summary:
{violations_json}

Write a concise developer-focused summary with:
- What to fix first (by priority)
- Common patterns in the violations
- Estimated effort level

Respond with plain text (no JSON), 3-5 paragraphs."""


# =====================================================
# OLLAMA CLIENT
# =====================================================

class OllamaClient:
    def __init__(self, base_url: str = None, model: str = None):
        self.base_url = base_url or settings.OLLAMA_BASE_URL
        self.model    = model    or settings.OLLAMA_DEFAULT_MODEL
        self.timeout  = settings.OLLAMA_TIMEOUT
        self.max_retries = settings.OLLAMA_MAX_RETRIES

    async def generate(self, prompt: str, model: str = None) -> str:
        """Call Ollama /api/generate with retry logic"""
        model = model or self.model
        payload = {
            "model":  model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.1,   # low temp for structured JSON
                "top_p": 0.9,
                "num_predict": 1500,
            }
        }

        for attempt in range(1, self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    logger.debug(f"Ollama request (attempt {attempt}): model={model}")
                    r = await client.post(
                        f"{self.base_url}/api/generate",
                        json=payload
                    )
                    r.raise_for_status()
                    data = r.json()
                    return data.get("response", "")

            except httpx.TimeoutException:
                logger.warning(f"Ollama timeout (attempt {attempt}/{self.max_retries})")
                if attempt < self.max_retries:
                    await asyncio.sleep(2 ** attempt)
                else:
                    raise

            except httpx.HTTPStatusError as e:
                logger.error(f"Ollama HTTP error: {e.response.status_code}")
                raise

            except Exception as e:
                logger.error(f"Ollama error (attempt {attempt}): {e}")
                if attempt < self.max_retries:
                    await asyncio.sleep(2)
                else:
                    raise

    async def is_available(self) -> bool:
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                r = await client.get(f"{self.base_url}/api/tags")
                return r.status_code == 200
        except Exception:
            return False

    def parse_json(self, text: str) -> Optional[dict]:
        """Robustly extract JSON from LLM response"""
        if not text:
            return None

        # Try direct parse first
        try:
            return json.loads(text.strip())
        except json.JSONDecodeError:
            pass

        # Strip markdown code fences
        cleaned = re.sub(r"```(?:json)?\s*", "", text)
        cleaned = re.sub(r"```\s*$", "", cleaned, flags=re.MULTILINE).strip()
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError:
            pass

        # Extract first {...} block
        match = re.search(r'\{[\s\S]*\}', text)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass

        logger.warning("Could not parse JSON from LLM response")
        return None


# =====================================================
# AI ANALYSIS SERVICE
# =====================================================

class AccessibilityAIService:
    def __init__(self, model: str = None):
        self.client = OllamaClient(model=model)
        self.model  = model or settings.OLLAMA_DEFAULT_MODEL

    async def analyze_violation(self, violation: dict) -> dict:
        """Generate AI analysis for a single violation"""
        nodes = violation.get("nodes", [])
        html_snippet = nodes[0].get("html", "N/A")[:500] if nodes else "N/A"

        prompt = VIOLATION_ANALYSIS_PROMPT.format(
            violation_id=violation.get("id", "unknown"),
            description=violation.get("description", ""),
            help_text=violation.get("help", ""),
            tags=", ".join(violation.get("tags", [])),
            severity=violation.get("severity", "medium"),
            html_snippet=html_snippet,
        )

        try:
            raw = await self.client.generate(prompt, model=self.model)
            parsed = self.client.parse_json(raw)
            if parsed:
                parsed["description"] = violation.get("description", "")
                if not parsed.get("sample_code_fix"):
                    parsed["sample_code_fix"] = self._build_sample_code_fix(violation)
                return parsed
            else:
                return self._fallback_analysis(violation)
        except Exception as e:
            logger.error(f"AI analysis failed for {violation.get('id')}: {e}")
            return self._fallback_analysis(violation)

    async def analyze_all_violations(self, violations: list, max_ai: int = 10) -> list:
        if not violations:
            return []
        
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_v = sorted(violations, key=lambda v: severity_order.get(v.get("severity","low"), 3))
        to_analyze = sorted_v[:max_ai]

        # Run up to 3 analyses in parallel instead of sequentially
        semaphore = asyncio.Semaphore(3)

        async def analyze_with_limit(v):
            async with semaphore:
                return await self.analyze_violation(v)

        results = await asyncio.gather(*[analyze_with_limit(v) for v in to_analyze])
        return list(results)

    async def generate_executive_summary(self, url: str, score: float, violations: list, metrics: dict) -> dict:
        """Generate executive summary with AI"""
        top_v = violations[:5]
        top_str = "\n".join([
            f"- [{v.get('severity','').upper()}] {v.get('description','')}"
            for v in top_v
        ])

        prompt = EXECUTIVE_SUMMARY_PROMPT.format(
            url=url,
            score=int(score),
            total=metrics.get("total", 0),
            critical=metrics.get("critical", 0),
            high=metrics.get("high", 0),
            medium=metrics.get("medium", 0),
            low=metrics.get("low", 0),
            passed=metrics.get("passed", 0),
            top_violations=top_str or "No violations found."
        )

        try:
            raw = await self.client.generate(prompt, model=self.model)
            parsed = self.client.parse_json(raw)
            return parsed or self._fallback_summary(url, score, metrics)
        except Exception as e:
            logger.error(f"Executive summary generation failed: {e}")
            return self._fallback_summary(url, score, metrics)

    def _fallback_analysis(self, violation: dict) -> dict:
        """Fallback when AI is unavailable"""
        sev = violation.get("severity", "medium")
        return {
            "issue_title":           violation.get("description", "Accessibility Issue"),
            "severity":              sev,
            "wcag_reference":        self._map_wcag(violation.get("tags", [])),
            "business_impact":       f"This {sev} accessibility issue may exclude users with disabilities and create legal risk.",
            "affected_users":        "Users relying on assistive technologies such as screen readers.",
            "technical_explanation": violation.get("help", "See the axe-core rule description for details."),
            "recommended_fix":       "Review the axe-core documentation and apply the suggested fix.",
            "sample_code_fix":       self._build_sample_code_fix(violation),
            "priority":              "P1" if sev == "critical" else ("P2" if sev == "high" else "P3"),
            "description":           violation.get("description", ""),
        }

    def _build_sample_code_fix(self, violation: dict) -> str:
        nodes = violation.get("nodes", [])
        html = nodes[0].get("html", "") if nodes else ""
        rule_id = violation.get("id", "")
        if rule_id in {"image-alt", "input-image-alt", "svg-img-alt"}:
            return '<img src="..." alt="Describe the image purpose here">'
        if rule_id in {"button-name", "input-button-name"}:
            return '<button type="button" aria-label="Describe the button action">...</button>'
        if rule_id in {"link-name", "duplicate-link"}:
            return '<a href="..." aria-label="Describe the destination or action">Visible link text</a>'
        if rule_id in {"label", "select-name"}:
            return '<label for="field-id">Field label</label>\n<input id="field-id" name="field-name" type="text">'
        if rule_id == "color-contrast":
            return '/* Increase foreground/background contrast to at least 4.5:1 for normal text */\n.selector { color: #1f2937; background-color: #ffffff; }'
        if rule_id == "aria-hidden-focus":
            return '<div aria-hidden="true">\n  <!-- Remove focusable controls from aria-hidden content, or remove aria-hidden. -->\n</div>'
        return html or "<!-- Apply the exact WCAG remediation to the failing element shown in the violation details. -->"

    def _fallback_summary(self, url: str, score: float, metrics: dict) -> dict:
        total = metrics.get("total", 0)
        return {
            "overview": f"The accessibility scan of {url} found {total} issue(s). The overall accessibility score is {int(score)}/100.",
            "key_findings": f"Critical issues: {metrics.get('critical',0)}, High: {metrics.get('high',0)}, Medium: {metrics.get('medium',0)}, Low: {metrics.get('low',0)}.",
            "recommendations": [
                "Address all critical violations immediately",
                "Fix high-severity issues in the next sprint",
                "Add alt text to all images",
                "Ensure all form fields have proper labels",
                "Verify keyboard navigation works throughout the site",
            ],
            "compliance_status": "Full WCAG 2.1 AA compliance audit required.",
            "score_reasoning":   f"Score of {int(score)} based on ratio of passed checks to total checks.",
        }

    def _map_wcag(self, tags: list) -> str:
        """Map axe-core tags to WCAG references"""
        wcag_map = {
            "wcag111": "WCAG 2.1 SC 1.1.1 — Non-text Content (Level A)",
            "wcag143": "WCAG 2.1 SC 1.4.3 — Contrast Minimum (Level AA)",
            "wcag211": "WCAG 2.1 SC 2.1.1 — Keyboard (Level A)",
            "wcag412": "WCAG 2.1 SC 4.1.2 — Name, Role, Value (Level A)",
            "wcag131": "WCAG 2.1 SC 1.3.1 — Info and Relationships (Level A)",
            "wcag241": "WCAG 2.1 SC 2.4.1 — Bypass Blocks (Level A)",
            "wcag244": "WCAG 2.1 SC 2.4.4 — Link Purpose (Level A)",
        }
        for tag in tags:
            if tag in wcag_map:
                return wcag_map[tag]
        return "WCAG 2.1"
