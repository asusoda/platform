"""The ASU sign-in: an officer signs in to ASU once, and agents read Sun Devil Central with the saved cookies.

browser.py runs Chromium through Playwright, an optional dependency. sso.py is the ASU sign-in on a page.
sundevil_central.py reads the club and event listings. service.py keeps the session as the org secret
asu_session and runs each sign-in attempt. This file registers the sign-in as asu, which the clubs and club_events
live queries read Sun Devil Central with.
"""

from modules.submodules import signins


def _usable(db, org_id: int) -> bool:
    from submodules.asu.signin import service

    return service.usable(db, org_id)


def _read(db, org_id: int, org_prefix: str, url: str):
    from submodules.asu.signin import service

    return service.read(db, org_id, org_prefix, url)


signins.register("asu", _usable, _read)
