"""Browser-capable page fetcher using Playwright locally with optional Browserless support."""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlencode

from app.config import (
    BROWSER_FETCHER_MODE,
    BROWSERLESS_API_TOKEN,
    BROWSERLESS_ENDPOINT,
    BROWSERLESS_PROXY,
    BROWSERLESS_SOLVE_CAPTCHAS,
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

        if self.mode == "browserless":
            return self._fetch_with_browserless(url)
        if self.mode == "auto":
            try:
                return self._fetch_with_local_playwright(url)
            except Exception as exc:
                logger.warning("Local Playwright fetch failed, trying Browserless: %s", exc)
                return self._fetch_with_browserless(url)
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

    def _fetch_with_browserless(self, url: str) -> BrowserFetchResult:
        """Connect Playwright to a Browserless-managed browser session."""
        if not BROWSERLESS_API_TOKEN:
            raise RuntimeError("Browserless mode requested but BROWSERLESS_API_TOKEN is not configured")

        from playwright.sync_api import sync_playwright

        endpoint = self._build_browserless_endpoint()

        with sync_playwright() as playwright:
            browser = playwright.chromium.connect_over_cdp(endpoint)
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
            return BrowserFetchResult(html=html, final_url=final_url, mode="browserless")

    def _build_browserless_endpoint(self) -> str:
        """Build the Browserless CDP endpoint with optional flags."""
        params = {"token": BROWSERLESS_API_TOKEN}
        if BROWSERLESS_PROXY:
            params["proxy"] = BROWSERLESS_PROXY
        if BROWSERLESS_SOLVE_CAPTCHAS:
            params["solveCaptchas"] = "true"
        return f"{BROWSERLESS_ENDPOINT}?{urlencode(params)}"
