"""Reusable rule engine for automated WCAG and enterprise checks."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

RULE_DIR = Path(__file__).resolve().parent
DEFAULT_RULES = RULE_DIR / "default_rules.json"
ENTERPRISE_RULES = RULE_DIR / "enterprise_rules.json"


class AccessibilityRuleEngine:
    """Evaluate built-in and configured custom accessibility rules."""

    def __init__(self, rules_path: Path | None = None):
        self.rules_path = rules_path or ENTERPRISE_RULES
        self.rules = self._load_rules()

    def evaluate(self, snapshot: dict[str, Any], axe_violations: list[dict[str, Any]]) -> dict[str, Any]:
        results = []
        for rule in self.rules:
            if not rule.get("enabled", True):
                continue
            try:
                results.append(self._evaluate_rule(rule, snapshot, axe_violations))
            except Exception as exc:
                logger.warning("Rule %s failed: %s", rule.get("id"), exc)
                results.append(self._result(rule, "manual_review", [str(exc)], "Rule execution failed."))

        summary = {
            "passed": sum(1 for r in results if r["status"] == "pass"),
            "failed": sum(1 for r in results if r["status"] == "fail"),
            "manual_review": sum(1 for r in results if r["status"] == "manual_review"),
            "total": len(results),
        }
        return {
            "engine_version": "1.0.0",
            "standard": "WCAG 2.1 AA plus enterprise custom rules",
            "generated_at": datetime.utcnow().isoformat(),
            "summary": summary,
            "results": results,
        }

    def _load_rules(self) -> list[dict[str, Any]]:
        rules = self._read_json(DEFAULT_RULES)
        if self.rules_path.exists():
            custom = self._read_json(self.rules_path)
            by_id = {r["id"]: r for r in rules}
            by_id.update({r["id"]: r for r in custom})
            rules = list(by_id.values())
        return rules

    def _read_json(self, path: Path) -> list[dict[str, Any]]:
        with open(path, "r", encoding="utf-8") as handle:
            return json.load(handle)

    def _evaluate_rule(self, rule: dict[str, Any], snapshot: dict[str, Any], axe_violations: list[dict[str, Any]]) -> dict[str, Any]:
        rule_type = rule.get("type", "builtin")
        if rule_type == "axe_proxy":
            return self._axe_proxy(rule, axe_violations)
        if rule_type == "selector":
            return self._selector_rule(rule, snapshot)
        if rule_type == "selector_count":
            return self._selector_count_rule(rule, snapshot)

        checks = {
            "keyboard.focusable-controls": self._keyboard_focusable_controls,
            "keyboard.tab-order": self._tab_order,
            "focus.visible": self._focus_visible,
            "labels.accessible-names": self._accessible_names,
            "aria.valid-usage": self._aria_valid_usage,
            "semantics.landmarks": self._semantic_landmarks,
            "headings.hierarchy": self._heading_hierarchy,
            "forms.labels-errors": self._form_accessibility,
            "images.alt-text": self._image_alt_text,
            "dialogs.accessible": self._dialog_accessibility,
            "errors.announced": self._error_messaging,
        }
        return checks[rule["id"]](rule, snapshot)

    def _result(self, rule: dict[str, Any], status: str, evidence: list[str], message: str = "") -> dict[str, Any]:
        return {
            "rule_id": rule.get("id"),
            "name": rule.get("name", rule.get("id")),
            "category": rule.get("category", "custom"),
            "wcag": rule.get("wcag", []),
            "severity": rule.get("severity", "medium"),
            "status": status,
            "message": message or ("Rule passed." if status == "pass" else "Rule failed."),
            "evidence": evidence,
        }

    def _fail_or_pass(self, rule: dict[str, Any], failures: list[str], pass_message: str) -> dict[str, Any]:
        if failures:
            return self._result(rule, "fail", failures[:20], f"{len(failures)} evidence item(s) failed.")
        return self._result(rule, "pass", [pass_message], pass_message)

    def _axe_proxy(self, rule: dict[str, Any], axe_violations: list[dict[str, Any]]) -> dict[str, Any]:
        ids = set(rule.get("axe_rule_ids", []))
        failures = [
            f"{v.get('id')}: {v.get('help') or v.get('description')} ({len(v.get('nodes', [])) or 1} element(s))"
            for v in axe_violations
            if v.get("id") in ids
        ]
        return self._fail_or_pass(rule, failures, "No matching axe-core violations were found.")

    def _selector_rule(self, rule: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        matches = [m for m in snapshot.get("customRuleMatches", []) if m.get("rule_id") == rule["id"]]
        failures = [f"{m.get('selector')}: {m.get('text') or m.get('html')}" for m in matches]
        return self._fail_or_pass(rule, failures, "No selector matches violated this custom rule.")

    def _selector_count_rule(self, rule: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        counts = snapshot.get("customRuleCounts", {})
        count = counts.get(rule["id"], 0)
        min_count = rule.get("min")
        max_count = rule.get("max")
        failed = (min_count is not None and count < min_count) or (max_count is not None and count > max_count)
        if failed:
            return self._result(rule, "fail", [f"Selector {rule.get('selector')} matched {count} element(s)."], rule.get("message", "Selector count outside configured bounds."))
        return self._result(rule, "pass", [f"Selector {rule.get('selector')} matched {count} element(s)."], "Selector count is within configured bounds.")

    def _keyboard_focusable_controls(self, rule: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        failures = []
        for el in snapshot.get("interactiveElements", []):
            if el.get("disabled") or el.get("hidden"):
                continue
            if not el.get("keyboardReachable"):
                failures.append(f"{el.get('selector')}: interactive {el.get('tag')} is not keyboard reachable.")
        return self._fail_or_pass(rule, failures, "All detected interactive controls are keyboard reachable.")

    def _tab_order(self, rule: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        failures = [
            f"{el.get('selector')}: positive tabindex={el.get('tabIndex')} can create an unexpected tab order."
            for el in snapshot.get("interactiveElements", [])
            if isinstance(el.get("tabIndex"), int) and el.get("tabIndex") > 0
        ]
        return self._fail_or_pass(rule, failures, "No positive tabindex values were detected.")

    def _focus_visible(self, rule: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        failures = [
            f"{el.get('selector')}: focus style appears visually hidden."
            for el in snapshot.get("interactiveElements", [])
            if el.get("keyboardReachable") and not el.get("focusVisible")
        ]
        return self._fail_or_pass(rule, failures, "Focusable elements expose a visible focus indicator.")

    def _accessible_names(self, rule: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        failures = [
            f"{el.get('selector')}: missing accessible name."
            for el in snapshot.get("interactiveElements", [])
            if el.get("requiresName") and not el.get("accessibleName")
        ]
        return self._fail_or_pass(rule, failures, "Controls and links have accessible names.")

    def _aria_valid_usage(self, rule: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        failures = []
        for el in snapshot.get("ariaElements", []):
            if el.get("hiddenFocusable"):
                failures.append(f"{el.get('selector')}: aria-hidden element contains focusable content.")
            if el.get("invalidRole"):
                failures.append(f"{el.get('selector')}: invalid role {el.get('role')}.")
            if el.get("missingRequiredName"):
                failures.append(f"{el.get('selector')}: role {el.get('role')} requires an accessible name.")
        return self._fail_or_pass(rule, failures, "ARIA usage checks did not detect invalid patterns.")

    def _semantic_landmarks(self, rule: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        landmarks = snapshot.get("landmarks", {})
        failures = []
        if landmarks.get("main", 0) != 1:
            failures.append(f"Expected exactly one main landmark; found {landmarks.get('main', 0)}.")
        if landmarks.get("nav", 0) == 0:
            failures.append("No navigation landmark detected.")
        if snapshot.get("genericButtonCount", 0):
            failures.append(f"{snapshot.get('genericButtonCount')} clickable div/span element(s) should use semantic buttons or links.")
        return self._fail_or_pass(rule, failures, "Semantic landmarks and controls are present.")

    def _heading_hierarchy(self, rule: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        headings = snapshot.get("headings", [])
        failures = []
        if not headings:
            failures.append("No headings were detected.")
        if headings and headings[0].get("level") != 1:
            failures.append(f"First heading is h{headings[0].get('level')} instead of h1.")
        previous = 0
        for heading in headings:
            level = heading.get("level", 0)
            if previous and level > previous + 1:
                failures.append(f"{heading.get('selector')}: heading jumps from h{previous} to h{level}.")
            previous = level
        return self._fail_or_pass(rule, failures, "Heading hierarchy is sequential.")

    def _form_accessibility(self, rule: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        failures = []
        for field in snapshot.get("formControls", []):
            if field.get("type") in ("hidden", "submit", "button", "reset"):
                continue
            if not field.get("accessibleName"):
                failures.append(f"{field.get('selector')}: form control has no accessible label.")
            if field.get("invalid") and not field.get("describedBy"):
                failures.append(f"{field.get('selector')}: invalid field is not associated with error/help text.")
        return self._fail_or_pass(rule, failures, "Form controls have labels and accessible error associations.")

    def _image_alt_text(self, rule: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        failures = [
            f"{img.get('selector')}: image is missing alt text."
            for img in snapshot.get("images", [])
            if not img.get("decorative") and not img.get("alt")
        ]
        return self._fail_or_pass(rule, failures, "Informative images include alt text or are marked decorative.")

    def _dialog_accessibility(self, rule: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        failures = []
        for dialog in snapshot.get("dialogs", []):
            if not dialog.get("accessibleName"):
                failures.append(f"{dialog.get('selector')}: dialog has no accessible name.")
            if dialog.get("role") == "dialog" and dialog.get("ariaModal") != "true":
                failures.append(f"{dialog.get('selector')}: modal dialog should set aria-modal=true.")
            if dialog.get("visible") and not dialog.get("hasFocusable"):
                failures.append(f"{dialog.get('selector')}: visible dialog has no focusable controls.")
        return self._fail_or_pass(rule, failures, "Dialogs are named and expose modal/focus affordances.")

    def _error_messaging(self, rule: dict[str, Any], snapshot: dict[str, Any]) -> dict[str, Any]:
        failures = []
        for error in snapshot.get("errors", []):
            if not error.get("announced"):
                failures.append(f"{error.get('selector')}: error text is not in an alert/status/live region.")
            if not error.get("associatedControl"):
                failures.append(f"{error.get('selector')}: error text is not associated with a control.")
        return self._fail_or_pass(rule, failures, "Detected error messages are announced and associated.")


def enterprise_rule_config_for_browser() -> list[dict[str, Any]]:
    rules = []
    if ENTERPRISE_RULES.exists():
        try:
            rules = json.loads(ENTERPRISE_RULES.read_text(encoding="utf-8"))
        except Exception:
            logger.warning("Could not read enterprise rules config", exc_info=True)
    return [
        {
            "id": r.get("id"),
            "type": r.get("type"),
            "selector": r.get("selector"),
            "fail_if_text_matches": r.get("fail_if_text_matches"),
        }
        for r in rules
        if r.get("enabled", True) and r.get("type") in {"selector", "selector_count"} and r.get("selector")
    ]
