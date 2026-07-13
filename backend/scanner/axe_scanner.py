"""
Accessibility Scanner — Playwright + axe-core
Runs Playwright in a separate thread to avoid Windows asyncio subprocess issues.
"""
import json
import base64
import logging
import asyncio
import concurrent.futures
from pathlib import Path
from typing import Optional

from backend.utils.config import settings

logger = logging.getLogger(__name__)

AXE_CORE_CDN = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js"

WCAG_CONFIG = {
    "A":   {"runOnly": {"type": "tag", "values": ["wcag2a"]}},
    "AA":  {"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa"]}},
    "AAA": {"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag2aaa"]}},
}

SEVERITY_MAP = {
    "critical": "critical",
    "serious":  "high",
    "moderate": "medium",
    "minor":    "low",
}


def _run_playwright_sync(url: str, wcag_level: str, depth: int, screenshot_path: Optional[str], headless: bool = True) -> dict:
    """Synchronous Playwright scan — runs inside a thread."""
    from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

    config = WCAG_CONFIG.get(wcag_level, WCAG_CONFIG["AA"])

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-dev-shm-usage",
                "--no-sandbox",
                "--disable-blink-features=AutomationControlled",
                "--disable-infobars",
                "--window-size=1366,768",
                "--start-maximized",
            ]
        )
        try:
            context = browser.new_context(
                viewport={"width": 1366, "height": 768},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="en-GB",
                timezone_id="Europe/London",
                # Mimic real browser permissions
                permissions=["geolocation"],
                extra_http_headers={
                    "Accept-Language": "en-GB,en;q=0.9",
                    "Accept-Encoding": "gzip, deflate, br",
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                    "Sec-Ch-Ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                    "Sec-Ch-Ua-Mobile": "?0",
                    "Sec-Ch-Ua-Platform": '"Windows"',
                    "Sec-Fetch-Dest": "document",
                    "Sec-Fetch-Mode": "navigate",
                    "Sec-Fetch-Site": "none",
                    "Upgrade-Insecure-Requests": "1",
                },
            )
            page = context.new_page()

            # Remove webdriver flag — main bot detection signal
            page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', { get: () => false });
                Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
                Object.defineProperty(navigator, 'languages', { get: () => ['en-GB', 'en'] });
                window.chrome = { runtime: {} };
            """)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=settings.SCAN_TIMEOUT * 1000)
                _wait_for_page_settle(page)
            except PlaywrightTimeout:
                logger.warning(f"Page load timeout for {url}, scanning partial content")

            # Auto-accept cookie banners
            _accept_cookies(page)
            _wait_for_page_settle(page, timeout_ms=10000)

            # Inject axe-core
            _inject_axe_sync(page)

            # FIX 1: unpack 3 values
            violations, passed_count, passes_detail = _run_axe_sync(page, config)
            page_records = [{
                "url": page.url,
                "requested_url": url,
                "violations": len(violations),
                "passes": passed_count,
                "diagnostics": _collect_page_diagnostics(page),
            }]

            # Screenshot
            screenshot_b64 = None
            if settings.SCREENSHOT_ENABLED:
                try:
                    if screenshot_path:
                        Path(screenshot_path).parent.mkdir(parents=True, exist_ok=True)
                        page.screenshot(path=screenshot_path, full_page=True)
                    else:
                        data = page.screenshot(full_page=True)
                        screenshot_b64 = base64.b64encode(data).decode()
                except Exception as e:
                    logger.warning(f"Screenshot failed: {e}")

            # Smart multi-page crawl — follows real user flows
            extra_screenshots = []
            if depth > 1:
                crawl_urls = _smart_crawl_urls(page, url, depth - 1)
                logger.info(f"Smart crawl: found {len(crawl_urls)} pages to scan")
                for i, link_url in enumerate(crawl_urls):
                    try:
                        logger.info(f"Scanning page {i+2}/{depth}: {link_url}")
                        page.goto(link_url, wait_until="domcontentloaded", timeout=40000)
                        page.wait_for_timeout(1500)
                        _accept_cookies(page)
                        _inject_axe_sync(page)
                        pv, pp, pd = _run_axe_sync(page, config)
                        violations.extend(pv)
                        passed_count += pp
                        passes_detail.extend(pd)
                        page_records.append({
                            "url": page.url,
                            "requested_url": link_url,
                            "violations": len(pv),
                            "passes": pp,
                            "diagnostics": _collect_page_diagnostics(page),
                        })
                        # Screenshot per page
                        if settings.SCREENSHOT_ENABLED and screenshot_path:
                            sp = screenshot_path.replace('.png', f'_p{i+2}.png')
                            try:
                                page.screenshot(path=sp, full_page=True)
                                extra_screenshots.append({
                                    'url': link_url,
                                    'path': sp,
                                    'captured_at': '',
                                })
                            except Exception:
                                pass
                    except Exception as e:
                        logger.warning(f"Failed to scan {link_url}: {e}")

            # FIX 3: include passes_detail and extra_screenshots in return dict
            return {
                "violations":        violations,
                "passed_count":      passed_count,
                "passes_detail":     passes_detail,
                "screenshot_b64":    screenshot_b64,
                "extra_screenshots": extra_screenshots,
                "page_records":      page_records,
            }

        finally:
            browser.close()


def _accept_cookies(page) -> None:
    """Auto-accept cookie consent banners."""
    selectors = [
        "button#onetrust-accept-btn-handler",
        "button[data-testid='cookie-accept']",
        "button[id*='accept-all']",
        "button[id*='acceptAll']",
        "button[class*='accept-all']",
        "button:has-text('Accept All Cookies')",
        "button:has-text('Accept All')",
        "button:has-text('Accept Cookies')",
        "button:has-text('Accept')",
        "button:has-text('I Accept')",
        "button:has-text('Allow All')",
        "button:has-text('Got it')",
        "button:has-text('OK')",
        "[aria-label*='Accept cookies']",
        "[aria-label*='accept all']",
    ]
    for sel in selectors:
        try:
            page.click(sel, timeout=1500)
            page.wait_for_timeout(600)
            logger.info(f"Cookie banner accepted via: {sel}")
            return
        except Exception:
            continue


def _wait_for_page_settle(page, timeout_ms: int = 15000) -> None:
    """Wait for post-load rendering without failing the whole scan on chatty sites."""
    for state in ("load", "networkidle"):
        try:
            page.wait_for_load_state(state, timeout=timeout_ms)
        except Exception:
            pass
    page.wait_for_timeout(3000)


def _collect_page_diagnostics(page) -> dict:
    """Collect cheap signals that help identify blocked or under-rendered scans."""
    try:
        return page.evaluate("""
            () => {
                const bodyText = (document.body && document.body.innerText || '').trim();
                const lowered = bodyText.toLowerCase();
                const blockerWords = [
                    'access denied', 'forbidden', 'verify you are human',
                    'unusual traffic', 'enable javascript', 'captcha',
                    'temporarily unavailable', 'request blocked'
                ];
                return {
                    final_url: location.href,
                    title: document.title || '',
                    ready_state: document.readyState,
                    body_text_length: bodyText.length,
                    link_count: document.querySelectorAll('a[href]').length,
                    button_count: document.querySelectorAll('button').length,
                    input_count: document.querySelectorAll('input, textarea, select').length,
                    image_count: document.querySelectorAll('img, picture, svg').length,
                    landmark_count: document.querySelectorAll('main, nav, header, footer, aside, [role="main"], [role="navigation"], [role="banner"], [role="contentinfo"]').length,
                    heading_count: document.querySelectorAll('h1,h2,h3,h4,h5,h6,[role="heading"]').length,
                    likely_blocked: blockerWords.some(word => lowered.includes(word)),
                    text_sample: bodyText.slice(0, 300)
                };
            }
        """)
    except Exception as e:
        logger.warning(f"Page diagnostics failed: {e}")
        return {"diagnostics_error": str(e)}


def _inject_axe_sync(page) -> None:
    """Inject axe-core from CDN."""
    try:
        already = page.evaluate("() => typeof window.axe !== 'undefined'")
        if already:
            return
        page.add_script_tag(url=AXE_CORE_CDN)
        page.wait_for_timeout(800)
        loaded = page.evaluate("() => typeof window.axe !== 'undefined'")
        if not loaded:
            raise RuntimeError("axe not loaded after CDN injection")
    except Exception as e:
        logger.warning(f"CDN injection failed ({e}), trying eval fallback")
        page.evaluate("""
            async () => {
                const r = await fetch('https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.9.1/axe.min.js');
                const txt = await r.text();
                eval(txt);
            }
        """)
        page.wait_for_timeout(1200)


def _run_axe_sync(page, config: dict) -> tuple:
    """Run axe-core and return (violations, passed_count, passes_detail)."""
    try:
        raw = page.evaluate(f"""
            async () => {{
                const results = await window.axe.run(document, {json.dumps(config)});
                return {{
                    violations: results.violations,
                    passes: results.passes.length,
                    passes_detail: results.passes.map(p => ({{
                        id: p.id,
                        description: p.description,
                        help: p.help,
                        helpUrl: p.helpUrl,
                        tags: p.tags,
                        nodes: p.nodes ? p.nodes.length : 0
                    }})),
                }};
            }}
        """)
        return (
            raw.get("violations", []),
            raw.get("passes", 0),
            raw.get("passes_detail", []),
        )
    except Exception as e:
        logger.error(f"axe run failed: {e}")
        return [], 0, []


class AccessibilityScanner:

    def __init__(self, headless: bool = True):
        self.headless = headless

    async def scan(
        self,
        url: str,
        wcag_level: str = "AA",
        depth: int = 1,
        screenshot_path: Optional[str] = None,
        on_step=None,
    ) -> dict:
        """Run Playwright scan in a thread — avoids Windows asyncio conflict."""
        async def step(name):
            if on_step:
                await on_step(name)

        await step("browser")
        loop = asyncio.get_event_loop()

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            await step("navigate")
            result = await loop.run_in_executor(
                pool,
                _run_playwright_sync,
                url,
                wcag_level,
                depth,
                screenshot_path,
                self.headless,
            )

        await step("axe_inject")
        await step("scanning")

        violations    = result["violations"]
        passed_count  = result["passed_count"]
        passes_detail = result.get("passes_detail", [])

        violations = self._deduplicate(violations)
        violations = [self._classify(v) for v in violations]

        # Deduplicate passed checks by rule id
        seen_p, unique_passes = set(), []
        for p in passes_detail:
            if p.get("id") not in seen_p:
                seen_p.add(p.get("id"))
                unique_passes.append(p)

        score   = self._calculate_score(violations, passed_count)
        page_records = result.get("page_records", [])
        metrics = self._build_metrics(violations, passed_count)
        metrics["quality"] = self._build_quality_report(
            url=url,
            violations=violations,
            passed_count=passed_count,
            passed_checks=unique_passes,
            page_records=page_records,
        )

        # FIX 4: include passed_checks in returned dict
        return {
            "violations":    violations,
            "passed_count":  passed_count,
            "passed_checks": unique_passes,
            "score":         score,
            "metrics":       metrics,
            "screenshot_b64": result.get("screenshot_b64"),
            "extra_screenshots": result.get("extra_screenshots", []),
        }

    def _classify(self, violation: dict) -> dict:
        impact = violation.get("impact", "moderate")
        violation["severity"]       = SEVERITY_MAP.get(impact, "medium")
        violation["wcag_reference"] = self._extract_wcag(violation.get("tags", []))
        return violation

    def _extract_wcag(self, tags: list) -> str:
        wcag_tags = [t for t in tags if t.startswith("wcag")]
        if wcag_tags:
            return wcag_tags[0].upper().replace("WCAG", "WCAG ")
        return "WCAG 2.1"

    def _deduplicate(self, violations: list) -> list:
        seen, unique = set(), []
        for v in violations:
            if v["id"] not in seen:
                seen.add(v["id"])
                unique.append(v)
        return unique

    def _calculate_score(self, violations: list, passed_count: int) -> float:
        weights = {"critical": 10, "high": 5, "medium": 2, "low": 1}
        penalty = sum(weights.get(v.get("severity", "low"), 1) for v in violations)
        total   = passed_count + penalty
        if total == 0:
            return 100.0
        return round(max(0, min(100, (passed_count / total) * 100)), 1)

    def _build_metrics(self, violations: list, passed_count: int) -> dict:
        metrics = {"critical": 0, "high": 0, "medium": 0, "low": 0, "passed": passed_count}
        for v in violations:
            sev = v.get("severity", "low")
            metrics[sev] = metrics.get(sev, 0) + 1
        metrics["total"] = len(violations)
        return metrics

    def _build_quality_report(
        self,
        url: str,
        violations: list,
        passed_count: int,
        passed_checks: list,
        page_records: list,
    ) -> dict:
        warnings = []
        first_diag = (page_records[0] or {}).get("diagnostics", {}) if page_records else {}
        page_count = len(page_records) or 1

        if not violations:
            warnings.append("No axe violations were found in the rendered DOM.")
        if not violations and passed_count < 35:
            warnings.append(f"Only {passed_count} axe pass results were reported; this is a low signal count for a modern retail page.")
        if first_diag.get("likely_blocked"):
            warnings.append("The page text contains common bot-blocking or access-denied language.")
        if first_diag.get("body_text_length", 0) and first_diag.get("body_text_length", 0) < 1000:
            warnings.append("The rendered page has very little visible text, which can indicate incomplete loading.")
        if first_diag.get("link_count", 0) and first_diag.get("link_count", 0) < 10:
            warnings.append("The rendered page has very few links for a commerce site.")
        if first_diag.get("input_count", 0) == 0 and any(term in url.lower() for term in ("shop", "store", "primark", "retail")):
            warnings.append("No form controls were detected; search, region, cart, or account controls may not have been exercised.")

        suspicious = bool(warnings) and (not violations or first_diag.get("likely_blocked"))
        return {
            "suspicious": suspicious,
            "warnings": warnings,
            "pages_scanned": page_count,
            "pass_rule_count": len(passed_checks),
            "element_counts": {
                "links": first_diag.get("link_count", 0),
                "buttons": first_diag.get("button_count", 0),
                "inputs": first_diag.get("input_count", 0),
                "images": first_diag.get("image_count", 0),
                "headings": first_diag.get("heading_count", 0),
                "landmarks": first_diag.get("landmark_count", 0),
                "body_text_length": first_diag.get("body_text_length", 0),
            },
            "page_records": page_records,
        }


def _smart_crawl_urls(page, base_url: str, max_pages: int) -> list:
    """
    Intelligently select pages to scan covering real user flows:
    - Product listing pages
    - Product detail pages
    - Cart / checkout
    - Search results
    - Contact / forms
    - Navigation subpages
    Prioritises variety over quantity.
    """
    from urllib.parse import urlparse
    base_host = urlparse(base_url).netloc

    # Priority URL patterns — highest value for accessibility testing
    priority_patterns = [
        # E-commerce flows
        r'/cart', r'/basket', r'/bag', r'/checkout',
        r'/search', r'/results',
        # Product pages (likely have images, forms)
        r'/product', r'/item', r'/p/', r'/shop',
        r'/category', r'/collection', r'/browse',
        # Navigation / important pages
        r'/contact', r'/help', r'/faq', r'/store',
        r'/account', r'/login', r'/sign', r'/register',
        r'/accessibility', r'/about',
    ]

    try:
        all_links = page.evaluate(f"""
            () => {{
                const seen = new Set();
                const links = [];
                document.querySelectorAll('a[href]').forEach(a => {{
                    const href = a.href;
                    if (!href || seen.has(href)) return;
                    if (!href.startsWith('http')) return;
                    try {{
                        const u = new URL(href);
                        if (u.hostname !== '{base_host}') return;
                        if (u.pathname === '/' || u.pathname === '') return;
                        // Skip file downloads, anchors, query-heavy URLs
                        if (u.pathname.match(/\\.(pdf|zip|jpg|png|gif|svg|css|js)$/i)) return;
                        seen.add(href);
                        links.push({{
                            url: href,
                            text: (a.textContent || '').trim().slice(0, 50),
                            path: u.pathname,
                        }});
                    }} catch (e) {{}}
                }});
                return links;
            }}
        """)

        if not all_links:
            return []

        # Score each URL by priority
        def score_url(link):
            path = link.get('path', '').lower()
            text = link.get('text', '').lower()
            score = 0
            for pattern in priority_patterns:
                if pattern in path or pattern in text:
                    score += 10
            # Penalise very long paths (deep pages)
            score -= len(path.split('/')) * 0.5
            return score

        scored = sorted(all_links, key=score_url, reverse=True)

        # Deduplicate by path structure (avoid scanning 50 product pages)
        seen_path_prefixes = set()
        selected = []
        for link in scored:
            path = link.get('path', '')
            # Take first 2 path segments as the "type"
            prefix = '/'.join(path.split('/')[:3])
            if prefix not in seen_path_prefixes:
                seen_path_prefixes.add(prefix)
                selected.append(link['url'])
            if len(selected) >= max_pages:
                break

        logger.info(f"Smart crawl selected: {selected}")
        return selected

    except Exception as e:
        logger.warning(f"Smart crawl URL extraction failed: {e}")
        return []
