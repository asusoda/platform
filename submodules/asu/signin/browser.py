"""The browser that signs in to ASU and loads Sun Devil Central pages with the saved cookies.

Browser is the interface that service.py uses; tests give a fake one. Chromium is the real one. It needs
the browser extra (uv sync --extra browser). core/browser.py opens it: the deployment's shared browser at
BROWSER_URL, else Chromium on this machine (playwright install chromium). Its guard answers every request
of the context from Python, so the browser reaches public addresses only.
"""

from __future__ import annotations

import importlib.util
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Protocol

from core import browser as browsers
from submodules.asu.signin import sso
from submodules.asu.signin.sso import Report, SignInFailed

NAV_MS = 60_000
DUO_SECONDS = 120.0
USER_AGENT = "PlatformASU/1.0 (+https://github.com/theaisocietyasu/bedrock)"
# The optional package that runs the browser
PACKAGE = "playwright"
INSTALL = "Install the browser extra on the API: uv sync --extra browser, then playwright install chromium"


@dataclass(frozen=True)
class Loaded:
    """One page load. state is the new session when the browser had to sign in to Sun Devil Central again."""

    url: str
    status: int
    html: str
    state: dict | None = None


class LoadFailed(Exception):
    """The page did not load. The message has no cookie in it."""


class Browser(Protocol):
    def sign_in(self, netid: str, password: str, report: Report) -> dict:
        """Signs in to ASU and Sun Devil Central. Returns the session (Playwright storage state)."""
        ...

    def load(self, state: dict, url: str) -> Loaded:
        """Loads url with the session in state."""
        ...


def missing() -> str | None:
    """Why this API cannot run the browser, or None when the Playwright package is installed."""
    if importlib.util.find_spec(PACKAGE) is None:
        return INSTALL
    return None


def _reason(error: Exception) -> str:
    if isinstance(error, browsers.BrowserConfigError):
        return str(error)
    text = str(error)
    if "Executable doesn't exist" in text:
        return "Chromium is not installed on the API. Run playwright install chromium"
    return text.strip().splitlines()[0][:300] if text.strip() else type(error).__name__


@contextmanager
def _chromium() -> Iterator[Any]:
    """A headless Chromium from core.browser: the shared browser at BROWSER_URL, else a local one."""
    with sso.api().sync_playwright() as playwright, browsers.open_browser(playwright) as browser:
        yield browser


def _context(browser: Any, **options: Any) -> Any:
    """A new context whose requests all go through the guard of core.browser."""
    context = browser.new_context(user_agent=USER_AGENT, **options)
    browsers.guard(context)
    return context


def _load(context: Any, url: str) -> Loaded:
    page = context.new_page()
    try:
        response = page.goto(url, wait_until="networkidle", timeout=NAV_MS)
        return Loaded(url=page.url, status=response.status if response else 0, html=page.content())
    finally:
        page.close()


class Chromium:
    """The Browser that runs headless Chromium through Playwright."""

    def sign_in(self, netid: str, password: str, report: Report) -> dict:
        try:
            with _chromium() as browser:
                context = _context(browser)
                page = context.new_page()
                page.goto(sso.LOGIN_URL, wait_until="networkidle", timeout=NAV_MS)
                if not sso.on_form(page):
                    raise SignInFailed("The ASU sign-in page did not show its form")
                sso.sign_in(page, netid, password, report, DUO_SECONDS)
                report("Signed in to ASU. Opening Sun Devil Central.", None)
                sso.enter_service(page, NAV_MS)
                loaded = _load(context, sso.CHECK_URL)
                if sso.is_login_url(loaded.url):
                    raise SignInFailed("Signed in to ASU, but Sun Devil Central still asks for a sign-in")
                return context.storage_state()
        except SignInFailed:
            raise
        except (sso.api().Error, browsers.BrowserConfigError) as e:
            raise SignInFailed(_reason(e)) from e

    def load(self, state: dict, url: str) -> Loaded:
        try:
            with _chromium() as browser:
                context = _context(browser, storage_state=state)
                loaded = _load(context, url)
                if not sso.is_login_url(loaded.url):
                    return loaded
                page = context.new_page()
                try:
                    sso.enter_service(page, NAV_MS)
                except SignInFailed:
                    return loaded
                finally:
                    page.close()
                again = _load(context, url)
                if sso.is_login_url(again.url):
                    return again
                return Loaded(url=again.url, status=again.status, html=again.html, state=context.storage_state())
        except (sso.api().Error, browsers.BrowserConfigError) as e:
            raise LoadFailed(_reason(e)) from e
