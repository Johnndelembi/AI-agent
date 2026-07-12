"""Browser-capable page fetcher using Playwright locally with optional Browserbase support."""

from __future__ import annotations

from dataclasses import dataclass

from app.config import (
    BROWSERBASE_API_KEY,
    BROWSERBASE_PROJECT_ID,
    BROWSERBASE_REGION,
    BROWSERBASE_USE_PROXY,
    BROWSERBASE_USE_VERIFIED,
    BROWSER_FETCHER_MODE,
    PLAYWRIGHT_BROWSER,
    PLAYWRIGHT_ENABLED,
    PLAYWRIGHT_HEADLESS,
    PLAYWRIGHT_TIMEOUT_MS,
    logger,
)


@dataclass
class BrowserFetchResult:
    """Browser fetch response payload."""

    html: str
    final_url: str
    mode: str


class BrowserFetchService:
    """Fetch pages through a real browser when plain HTTP is blocked."""

    def __init__(self):
        self.enabled = PLAYWRIGHT_ENABLED
        self.mode = (BROWSER_FETCHER_MODE or "local").lower()
        self.browser_name = PLAYWRIGHT_BROWSER
        self.headless = PLAYWRIGHT_HEADLESS
        self.timeout_ms = PLAYWRIGHT_TIMEOUT_MS

    def fetch_html(self, url: str) -> BrowserFetchResult:
        """Fetch HTML through the configured browser backend."""
        if not self.enabled:
            raise RuntimeError("Browser fetch fallback is disabled")

        if self.mode == "browserbase":
            return self._fetch_with_browserbase(url)
        if self.mode == "auto":
            try:
                return self._fetch_with_local_playwright(url)
            except Exception as exc:
                logger.warning("Local Playwright fetch failed, trying Browserbase: %s", exc)
                return self._fetch_with_browserbase(url)
        return self._fetch_with_local_playwright(url)

    def _fetch_with_local_playwright(self, url: str) -> BrowserFetchResult:
        """Run a local headless browser with Playwright."""
        from playwright.sync_api import sync_playwright

        with sync_playwright() as playwright:
            browser_launcher = getattr(playwright, self.browser_name)
            browser = browser_launcher.launch(
                headless=self.headless,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            context = browser.new_context(ignore_https_errors=True)
            page = context.new_page()
            page.set_default_timeout(self.timeout_ms)
            page.set_extra_http_headers(
                {
                    "Accept-Language": "en-US,en;q=0.9",
                }
            )
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                page.wait_for_load_state("networkidle", timeout=self.timeout_ms)
            except Exception:
                # Some challenge pages never settle on networkidle; continue with current DOM.
                pass

            html = page.content()
            final_url = page.url
            context.close()
            browser.close()
            return BrowserFetchResult(html=html, final_url=final_url, mode="local_playwright")

    def _fetch_with_browserbase(self, url: str) -> BrowserFetchResult:
        """Connect Playwright to a Browserbase-managed browser session."""
        if not BROWSERBASE_API_KEY:
            raise RuntimeError("Browserbase mode requested but BROWSERBASE_API_KEY is not configured")

        from browserbase import Browserbase
        from playwright.sync_api import sync_playwright

        bb = Browserbase(api_key=BROWSERBASE_API_KEY)
        session_kwargs = {}
        if BROWSERBASE_PROJECT_ID:
            session_kwargs["project_id"] = BROWSERBASE_PROJECT_ID
        if BROWSERBASE_REGION:
            session_kwargs["region"] = BROWSERBASE_REGION

        browser_settings = {
            "recordSession": True,
            "logSession": True,
        }
        if BROWSERBASE_USE_VERIFIED:
            browser_settings["verified"] = True
        if browser_settings:
            session_kwargs["browser_settings"] = browser_settings
        if BROWSERBASE_USE_PROXY:
            session_kwargs["proxies"] = True

        session = bb.sessions.create(**session_kwargs)

        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(session.connect_url)
            context = browser.contexts[0] if browser.contexts else browser.new_context(ignore_https_errors=True)
            page = context.pages[0] if context.pages else context.new_page()
            page.set_default_timeout(self.timeout_ms)
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=self.timeout_ms)
                page.wait_for_load_state("networkidle", timeout=self.timeout_ms)
            except Exception:
                pass

            html = page.content()
            final_url = page.url
            browser.close()
            return BrowserFetchResult(html=html, final_url=final_url, mode="browserbase")
