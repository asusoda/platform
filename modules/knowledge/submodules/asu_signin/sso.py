"""The ASU sign-in on a browser page: the ASU sign-in form, then Duo, then the Sun Devil Central sign-in link.

The functions take a Playwright page. Playwright is imported only when a function runs. Nothing here keeps
the NetID or the password.
"""

from __future__ import annotations

import importlib
import re
import time
from collections.abc import Callable
from functools import cache
from types import ModuleType
from typing import Any
from urllib.parse import urlsplit

# The page that starts the sign-in; it sends the browser to the ASU sign-in form.
LOGIN_URL = "https://my.asu.edu/"
# The Sun Devil Central sign-in page, and the link on it that starts the ASU sign-in.
SERVICE_LOGIN_URL = "https://sundevilcentral.eoss.asu.edu/webapp/auth/login"
SERVICE_SSO_TEXT = "SSO Login"
# A page that loads only with a session; the sign-in checks the session on it.
CHECK_URL = "https://sundevilcentral.eoss.asu.edu/events"
# Hosts that a sign-in goes through. A page on one of them has not finished the sign-in.
SSO_HOSTS = ("weblogin.asu.edu", "duosecurity.com", "campusgroups.com")
# Hosts and paths of sign-in pages. A page that ends on one of them has no session.
LOGIN_HOSTS = ("weblogin.asu.edu", "cas.asu.edu", "login.microsoftonline.com", "idp.asu.edu")
LOGIN_PATHS = ("/webapp/auth/login",)

_USERNAME = "#username"
_PASSWORD = "#password"  # nosec B105 - a CSS selector, not a password
_SUBMIT = "button[name=submitBtn]"
_FORM_ERROR = ".alert-danger, .banner-danger, #loginErrorsPanel, .login-error"
_DUO_HOST = "duosecurity.com"
_DUO_CODE = ".verification-code, [class*=verification-code], [data-testid*=code]"
_CODE_DIGITS = re.compile(r"(?<!\d)\d{3,8}(?!\d)")
_DUO_TRUST = "#trust-browser-button"
_DUO_TRUST_LABEL = re.compile(r"^\s*yes\b", re.IGNORECASE)
_DUO_HEADING = "h1, h2"
_POLL_SECONDS = 0.5
_SETTLE_MS = 15_000

# Gets a progress message and, when Duo shows one, the verification code.
Report = Callable[[str, str | None], None]


class SignInFailed(Exception):
    """The sign-in stopped. The message is a plain reason for the officer, with no NetID or password in it."""


class BadPassword(SignInFailed):
    """The ASU sign-in form did not accept the NetID or the password."""


@cache
def api() -> ModuleType:
    """playwright.sync_api, imported on first use."""
    return importlib.import_module("playwright.sync_api")


def host_of(url: str) -> str:
    return (urlsplit(url).hostname or "").lower()


def on_host(url: str, hosts: tuple[str, ...]) -> bool:
    """Whether url is on one of hosts or on a subdomain of one."""
    host = host_of(url)
    return any(host == h or host.endswith("." + h) for h in hosts)


def is_login_url(url: str) -> bool:
    """Whether url is a sign-in page. A load that ends on one has no session."""
    if on_host(url, LOGIN_HOSTS):
        return True
    path = urlsplit(url).path.lower().rstrip("/")
    return any(path == p.rstrip("/") for p in LOGIN_PATHS)


def on_form(page: Any) -> bool:
    """Whether the page shows the ASU NetID and password form."""
    if not on_host(page.url, ("weblogin.asu.edu",)):
        return False
    try:
        field = page.locator(_PASSWORD).first
        return field.count() > 0 and field.is_visible()
    except api().Error:
        return False


def sign_in(page: Any, netid: str, password: str, report: Report, duo_seconds: float) -> None:
    """Fills the ASU form on page, submits it, and waits for Duo until the page leaves the sign-in hosts."""
    page.fill(_USERNAME, netid)
    page.fill(_PASSWORD, password)
    page.click(_SUBMIT)
    settle(page)
    if on_form(page):
        raise BadPassword(_text(page, _FORM_ERROR) or "ASU did not accept the NetID or the password")
    report("Password accepted. Approve the Duo push on your phone.", None)
    _await_duo(page, report, duo_seconds)


def _await_duo(page: Any, report: Report, duo_seconds: float) -> None:
    """Polls until the page leaves the sign-in hosts. Reports each new Duo code and heading."""
    deadline = time.monotonic() + duo_seconds
    said: set[str] = set()
    trusted = False
    while on_host(page.url, SSO_HOSTS):
        if time.monotonic() > deadline:
            raise SignInFailed(f"Duo was not approved within {int(duo_seconds)} seconds")
        if on_host(page.url, (_DUO_HOST,)):
            code = _duo_code(page)
            if code and code not in said:
                said.add(code)
                report(f"Enter the code {code} in the Duo app.", code)
            heading = _text(page, _DUO_HEADING)
            if heading and heading not in said:
                said.add(heading)
                report(f"Duo: {heading}", code or None)
            if not trusted and _trust(page):
                trusted = True
                report("Duo approved. Finishing the sign-in.", None)
        page.wait_for_timeout(int(_POLL_SECONDS * 1000))
    settle(page)


def _duo_code(page: Any) -> str:
    """The Verified Duo Push code on the page: from its own element, else from the digits in the page text."""
    code = _CODE_DIGITS.search(_text(page, _DUO_CODE))
    if code:
        return code.group(0)
    body = _text(page, "body")
    if "code" not in body.lower():
        return ""
    code = _CODE_DIGITS.search(body)
    return code.group(0) if code else ""


def enter_service(page: Any, nav_ms: int) -> None:
    """Opens the Sun Devil Central sign-in page and follows its ASU sign-in link with the ASU session."""
    page.goto(SERVICE_LOGIN_URL, wait_until="networkidle", timeout=nav_ms)
    if not is_login_url(page.url):
        return
    link = page.get_by_text(SERVICE_SSO_TEXT, exact=False).first
    if link.count() == 0:
        raise SignInFailed(f"The Sun Devil Central sign-in page has no {SERVICE_SSO_TEXT} link")
    link.click()
    settle(page)
    if on_form(page):
        raise SignInFailed("The ASU session has expired")
    try:
        page.wait_for_url(lambda u: not on_host(u, SSO_HOSTS) and not is_login_url(u), timeout=nav_ms)
    except api().Error as e:
        raise SignInFailed("The ASU session has expired") from e


def settle(page: Any) -> None:
    """Waits for the page to stop loading. A page that keeps polling is left as it is."""
    try:
        page.wait_for_load_state("networkidle", timeout=_SETTLE_MS)
    except api().TimeoutError:
        return


def _text(page: Any, selector: str) -> str:
    """The text of the first visible match of selector, or empty while the page moves."""
    try:
        for el in page.locator(selector).all():
            if el.is_visible():
                text = " ".join(el.inner_text(timeout=1_000).split())
                if text:
                    return text
    except api().Error:
        return ""
    return ""


def _trust(page: Any) -> bool:
    """Answers yes when Duo asks whether this is your device, by the button id or by its label."""
    if _click(page, _DUO_TRUST):
        return True
    try:
        button = page.get_by_role("button", name=_DUO_TRUST_LABEL).first
        if button.count() == 0 or not button.is_visible():
            return False
        button.click(timeout=5_000)
    except api().Error:
        return False
    return True


def _click(page: Any, selector: str) -> bool:
    """Clicks the first visible match of selector. False when there is none or the page moved."""
    try:
        el = page.locator(selector).first
        if el.count() == 0 or not el.is_visible():
            return False
        el.click(timeout=5_000)
    except api().Error:
        return False
    return True
