"""AI-powered accessibility scenario generation using open-source local LLMs."""
import json
import logging
from typing import Any

from backend.ai_engine.ollama_service import OllamaClient

logger = logging.getLogger(__name__)


SCENARIO_PROMPT = """You are an accessibility test architect.
Generate accessibility test scenarios from this page evidence.

URL: {url}
DOM summary:
{dom_summary}

Axe violations:
{violations}

Rule engine findings:
{rule_results}

Generate scenarios for these categories:
- Keyboard-only users
- Screen reader users
- Low vision users
- Color blind users
- Cognitive accessibility
- Mobile accessibility
- Zoom/responsive accessibility

Respond ONLY with a JSON array. Each item must use this exact structure:
{{
  "test_case_id": "A11Y-001",
  "category": "Keyboard-only users",
  "scenario_description": "Clear scenario",
  "steps": ["Step 1", "Step 2"],
  "expected_result": "Expected accessible behavior",
  "wcag_mapping": ["WCAG 2.1 SC 2.1.1"],
  "severity": "critical|high|medium|low",
  "automation_feasibility": "automated|semi-automated|manual",
  "negative_test": true,
  "likely_risk": "Risk this scenario targets"
}}
Return 10 to 14 scenarios with practical edge cases and negative tests."""


class AccessibilityScenarioService:
    def __init__(self, model: str = "llama3"):
        self.model = model
        self.client = OllamaClient(model=model)

    async def generate_scenarios(
        self,
        url: str,
        dom_snapshot: dict[str, Any],
        violations: list[dict[str, Any]],
        rule_results: dict[str, Any],
    ) -> list[dict[str, Any]]:
        prompt = SCENARIO_PROMPT.format(
            url=url,
            dom_summary=json.dumps(self._summarize_dom(dom_snapshot), indent=2)[:6000],
            violations=json.dumps(self._summarize_violations(violations), indent=2)[:5000],
            rule_results=json.dumps(rule_results.get("results", [])[:20], indent=2)[:5000],
        )
        try:
            raw = await self.client.generate(prompt, model=self.model)
            parsed = self._parse_array(raw)
            if parsed:
                return self._normalize(parsed)
        except Exception as exc:
            logger.warning("AI scenario generation failed, using fallback: %s", exc)
        return self._fallback_scenarios(dom_snapshot, violations, rule_results)

    def _parse_array(self, text: str) -> list[dict[str, Any]] | None:
        if not text:
            return None
        cleaned = text.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
        try:
            data = json.loads(cleaned)
        except json.JSONDecodeError:
            start = cleaned.find("[")
            end = cleaned.rfind("]")
            if start == -1 or end == -1:
                return None
            try:
                data = json.loads(cleaned[start:end + 1])
            except json.JSONDecodeError:
                return None
        return data if isinstance(data, list) else None

    def _normalize(self, scenarios: list[dict[str, Any]]) -> list[dict[str, Any]]:
        normalized = []
        for idx, scenario in enumerate(scenarios[:20], start=1):
            normalized.append({
                "test_case_id": scenario.get("test_case_id") or f"A11Y-{idx:03d}",
                "category": scenario.get("category", "Accessibility"),
                "scenario_description": scenario.get("scenario_description", ""),
                "steps": scenario.get("steps") if isinstance(scenario.get("steps"), list) else [],
                "expected_result": scenario.get("expected_result", ""),
                "wcag_mapping": scenario.get("wcag_mapping") if isinstance(scenario.get("wcag_mapping"), list) else [],
                "severity": scenario.get("severity", "medium"),
                "automation_feasibility": scenario.get("automation_feasibility", "semi-automated"),
                "negative_test": bool(scenario.get("negative_test", False)),
                "likely_risk": scenario.get("likely_risk", ""),
            })
        return normalized

    def _summarize_dom(self, dom_snapshot: dict[str, Any]) -> dict[str, Any]:
        return {
            "title": dom_snapshot.get("title"),
            "landmarks": dom_snapshot.get("landmarks", {}),
            "headings": dom_snapshot.get("headings", [])[:20],
            "interactive_count": len(dom_snapshot.get("interactiveElements", [])),
            "form_control_count": len(dom_snapshot.get("formControls", [])),
            "image_count": len(dom_snapshot.get("images", [])),
            "dialog_count": len(dom_snapshot.get("dialogs", [])),
            "error_message_count": len(dom_snapshot.get("errors", [])),
        }

    def _summarize_violations(self, violations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [
            {
                "id": v.get("id"),
                "description": v.get("description"),
                "severity": v.get("severity"),
                "wcag": v.get("wcag_reference"),
                "nodes": len(v.get("nodes", [])),
            }
            for v in violations[:25]
        ]

    def _fallback_scenarios(
        self,
        dom_snapshot: dict[str, Any],
        violations: list[dict[str, Any]],
        rule_results: dict[str, Any],
    ) -> list[dict[str, Any]]:
        failed_rules = [r for r in rule_results.get("results", []) if r.get("status") == "fail"]
        scenarios = [
            self._scenario(1, "Keyboard-only users", "Navigate the page using Tab, Shift+Tab, Enter, Space, and Escape.", ["Load the page.", "Use Tab to move through every interactive element.", "Activate buttons, links, menus, and dialogs using the keyboard."], "Focus moves in a logical order, controls are operable, no keyboard trap occurs, and focus is always visible.", ["WCAG 2.1 SC 2.1.1", "WCAG 2.1 SC 2.4.3", "WCAG 2.1 SC 2.4.7"], "high", "semi-automated", True, "Keyboard traps, unreachable controls, or invisible focus indicators."),
            self._scenario(2, "Screen reader users", "Verify all controls, links, images, headings, and regions expose useful names and roles.", ["Open the page with a screen reader.", "Navigate by headings, landmarks, links, buttons, and form controls.", "Listen for role, name, state, and error announcements."], "Assistive technology announces meaningful labels, roles, states, headings, landmarks, and changes.", ["WCAG 2.1 SC 1.3.1", "WCAG 2.1 SC 4.1.2"], "high", "semi-automated", False, "Missing labels or invalid ARIA can make workflows unusable."),
            self._scenario(3, "Low vision users", "Validate text, controls, and focus indicators at 200 percent zoom.", ["Set browser zoom to 200 percent.", "Use the primary workflow.", "Check for clipping, hidden controls, horizontal scrolling, or overlapped content."], "Content reflows without loss of information or functionality.", ["WCAG 2.1 SC 1.4.4", "WCAG 2.1 SC 1.4.10"], "medium", "manual", False, "Zoomed layouts may hide controls or obscure status messages."),
            self._scenario(4, "Color blind users", "Confirm status, errors, selected states, and charts do not rely on color alone.", ["Identify all states indicated by color.", "Switch to a color blindness simulation or grayscale.", "Verify text, icons, patterns, or labels communicate the same information."], "Information remains understandable without color perception.", ["WCAG 2.1 SC 1.4.1"], "medium", "manual", True, "Color-only feedback can hide defects, errors, or required actions."),
            self._scenario(5, "Cognitive accessibility", "Review instructions, error messages, and recovery paths for clarity.", ["Trigger validation errors.", "Read instructions and remediation text.", "Confirm the user can recover without losing data."], "Errors identify the field, explain the issue, and provide clear correction guidance.", ["WCAG 2.1 SC 3.3.1", "WCAG 2.1 SC 3.3.3"], "medium", "manual", True, "Ambiguous errors increase task abandonment and support burden."),
            self._scenario(6, "Mobile accessibility", "Validate the same workflow with touch and a narrow viewport.", ["Open the page at 390px width.", "Use touch to complete the primary workflow.", "Check target size, focus order, and accessible names."], "Touch targets are usable and mobile layout keeps all content accessible.", ["WCAG 2.1 SC 1.4.10", "WCAG 2.1 SC 2.5.5"], "medium", "semi-automated", False, "Responsive changes can remove landmarks, labels, or controls."),
            self._scenario(7, "Zoom/responsive accessibility", "Check high-zoom responsive behavior at 320 CSS pixels.", ["Set viewport width to 320px.", "Zoom to 400 percent if supported.", "Navigate all page sections and dialogs."], "No two-dimensional scrolling is needed for normal content and all controls remain reachable.", ["WCAG 2.1 SC 1.4.10"], "high", "semi-automated", False, "Reflow failures block low-vision users."),
        ]
        for idx, rule in enumerate(failed_rules[:5], start=len(scenarios) + 1):
            scenarios.append(self._scenario(
                idx,
                rule.get("category", "Accessibility"),
                f"Regression test for failed rule: {rule.get('name')}.",
                ["Load the affected page.", "Inspect the evidence item from the latest scan.", "Repeat the user interaction that exposes the failure."],
                "The rule passes and each evidence item is remediated.",
                [f"WCAG 2.1 SC {wcag}" for wcag in rule.get("wcag", [])],
                rule.get("severity", "medium"),
                "automated",
                True,
                rule.get("message", "Detected rule failure."),
            ))
        if violations:
            top = violations[0]
            scenarios.append(self._scenario(
                len(scenarios) + 1,
                "Edge-case accessibility validations",
                f"Negative test for axe finding: {top.get('description')}.",
                ["Open the page.", "Locate the affected component.", "Verify the failure cannot recur after remediation."],
                "The component satisfies the mapped WCAG criterion and no equivalent violation is reported.",
                [top.get("wcag_reference", "WCAG 2.1")],
                top.get("severity", "medium"),
                "automated",
                True,
                top.get("help", "A recurring automated violation is likely."),
            ))
        return scenarios

    def _scenario(
        self,
        idx: int,
        category: str,
        description: str,
        steps: list[str],
        expected: str,
        wcag: list[str],
        severity: str,
        feasibility: str,
        negative: bool,
        risk: str,
    ) -> dict[str, Any]:
        return {
            "test_case_id": f"A11Y-{idx:03d}",
            "category": category,
            "scenario_description": description,
            "steps": steps,
            "expected_result": expected,
            "wcag_mapping": wcag,
            "severity": severity,
            "automation_feasibility": feasibility,
            "negative_test": negative,
            "likely_risk": risk,
        }
