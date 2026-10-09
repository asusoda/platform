"""The ASU sign-in: an officer signs in to ASU once, and agents read Sun Devil Central with the saved cookies.

browser.py runs Chromium through Playwright, an optional dependency. sso.py is the ASU sign-in on a page.
sundevil_central.py reads the club and event listings. service.py keeps the session as the org secret
asu_session and runs each sign-in attempt. tools.py gives agents asu.clubs and asu.events.
"""
