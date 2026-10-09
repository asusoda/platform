"""Google tools for agents: Calendar, Drive, Sheets and Gmail with the org's service account. No Flask here.

The tools use only the org's own service account key, never the deployment default, so an agent reads only
its own org's Google data. With a Workspace user set on the Integrations page, the service account acts as
that user through domain-wide delegation. Gmail works only then, because a service account has no mailbox.
"""

import base64
import json
from datetime import UTC, datetime
from email.message import EmailMessage
from typing import Any
from urllib.parse import quote

import requests
from google.auth.exceptions import GoogleAuthError
from google.auth.transport.requests import AuthorizedSession
from google.oauth2 import service_account

from core.integrations import registry
from core.tools import ToolError, tool
from modules.auth import scopes
from modules.calendar.integrations import GOOGLE_SECRET, GOOGLE_SUBJECT

TIMEOUT_SECONDS = 30
MAX_TEXT_CHARS = 100_000
MAX_DOWNLOAD_BYTES = 5_000_000
MAX_ROWS = 500

CALENDAR = "https://www.googleapis.com/auth/calendar"
DRIVE_READ = "https://www.googleapis.com/auth/drive.readonly"
SHEETS = "https://www.googleapis.com/auth/spreadsheets"
GMAIL_READ = "https://www.googleapis.com/auth/gmail.readonly"
GMAIL_SEND = "https://www.googleapis.com/auth/gmail.send"

CALENDAR_API = "https://www.googleapis.com/calendar/v3"
DRIVE_API = "https://www.googleapis.com/drive/v3"
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
GMAIL_API = "https://gmail.googleapis.com/gmail/v1/users/me"

# Google Docs, Sheets and Slides export as text; Sheets export the first sheet only
EXPORTS = {
    "application/vnd.google-apps.document": "text/plain",
    "application/vnd.google-apps.spreadsheet": "text/csv",
    "application/vnd.google-apps.presentation": "text/plain",
}

registry.use("google", "integrations")
scopes.declare("google:read", "Read the org's Google Calendar events, Drive files and Sheets", "google")
scopes.declare(
    "google:write", "Create and change Calendar events, Drive files and Sheets rows (with confirm)", "google"
)
scopes.declare(
    "gmail:read", "Search and read the Gmail of the account signed in with Google or the Workspace user", "google"
)
scopes.declare("gmail:send", "Send mail, write drafts and label mail as that account (with confirm)", "google")


def connected(db, org_id: int) -> bool:
    """The org saved its own service account key."""
    return registry.org_values(db, org_id, "google") is not None


def delegated(db, org_id: int) -> bool:
    """The org saved a key and a Workspace user to act as."""
    saved = registry.org_values(db, org_id, "google")
    return bool(saved and saved.get(GOOGLE_SUBJECT))


def session(db, org_id: int, scope: str) -> AuthorizedSession:
    """An HTTP session signed in with the org's service account for one Google API scope."""
    saved = registry.org_values(db, org_id, "google")
    if saved is None:
        raise ToolError("Connect Google on the Integrations page first", 409)
    try:
        info = json.loads(saved[GOOGLE_SECRET])
        credentials = service_account.Credentials.from_service_account_info(info, scopes=[scope])
    except (ValueError, KeyError, TypeError, GoogleAuthError) as e:
        raise ToolError("The org's Google service account key is not valid", 409) from e
    subject = saved.get(GOOGLE_SUBJECT)
    if subject:
        credentials = credentials.with_subject(subject)
    return AuthorizedSession(credentials)


def _reason(response: requests.Response) -> str:
    try:
        error = response.json().get("error")
    except (ValueError, AttributeError):
        return response.text.strip()[:300]
    if isinstance(error, dict):
        return str(error.get("message") or "")[:300]
    return str(error or "")[:300]


def call(db, org, scope: str, method: str, url: str, **kwargs: Any) -> requests.Response:
    """One Google API request. Raises ToolError with Google's reason when it fails."""
    signed = session(db, int(org.id), scope)
    try:
        response = signed.request(method, url, timeout=TIMEOUT_SECONDS, **kwargs)
    except GoogleAuthError as e:
        raise ToolError(
            "Google refused the service account. With a Workspace user set, the Workspace admin must allow "
            f"the service account's client ID the scope {scope} under domain-wide delegation",
            403,
        ) from e
    except requests.RequestException as e:
        raise ToolError("Google could not be reached", 502) from e
    if response.status_code == 404:
        raise ToolError("Google found nothing there, or it is not shared with the service account", 404)
    if response.status_code in (401, 403):
        raise ToolError(f"Google refused: {_reason(response)}", 403)
    if response.status_code >= 400:
        raise ToolError(f"Google answered {response.status_code}: {_reason(response)}", 422)
    return response


def _text(value: str) -> dict:
    return {"text": value[:MAX_TEXT_CHARS], "truncated": len(value) > MAX_TEXT_CHARS}


def _when(value: str) -> dict:
    """A Calendar start or end: a date for YYYY-MM-DD, else a date and time."""
    return {"date": value} if len(value) == 10 else {"dateTime": value}


def _event(item: dict) -> dict:
    return {
        "id": item.get("id"),
        "summary": item.get("summary"),
        "start": item.get("start"),
        "end": item.get("end"),
        "location": item.get("location"),
        "description": str(item.get("description") or "")[:2000],
        "link": item.get("htmlLink"),
    }


CALENDAR_ID = {"type": "string", "minLength": 1, "maxLength": 500, "description": "Default primary"}
TIME = {"type": "string", "minLength": 10, "maxLength": 40, "description": "RFC 3339, or YYYY-MM-DD for all day"}
ID = {"type": "string", "minLength": 1, "maxLength": 500}


@tool(
    "google.calendar_list",
    description="The calendars the org's Google account sees. A calendar shared with a service account "
    "does not show here until it is added; call google.calendar_events with its ID.",
    scope="google:read",
    input_schema={"type": "object", "properties": {}, "additionalProperties": False},
    integration="google",
    available=connected,
)
def calendar_list(db, org, caller):
    found = call(db, org, CALENDAR, "GET", f"{CALENDAR_API}/users/me/calendarList").json()
    return {
        "calendars": [
            {"id": c.get("id"), "summary": c.get("summary"), "access": c.get("accessRole")}
            for c in found.get("items") or []
        ]
    }


@tool(
    "google.calendar_events",
    description="Events of a Google calendar in time order, from time_min (default now) to time_max.",
    scope="google:read",
    input_schema={
        "type": "object",
        "properties": {
            "calendar_id": CALENDAR_ID,
            "time_min": TIME,
            "time_max": TIME,
            "query": {"type": "string", "maxLength": 200},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 50},
        },
        "additionalProperties": False,
    },
    integration="google",
    available=connected,
)
def calendar_events(
    db,
    org,
    caller,
    calendar_id: str = "primary",
    time_min: str | None = None,
    time_max: str | None = None,
    query: str | None = None,
    max_results: int = 20,
):
    params: dict[str, Any] = {"singleEvents": "true", "orderBy": "startTime", "maxResults": max_results}
    if time_min:
        params["timeMin"] = time_min if len(time_min) > 10 else f"{time_min}T00:00:00Z"
    else:
        params["timeMin"] = datetime.now(UTC).isoformat()
    if time_max:
        params["timeMax"] = time_max if len(time_max) > 10 else f"{time_max}T23:59:59Z"
    if query:
        params["q"] = query
    url = f"{CALENDAR_API}/calendars/{quote(calendar_id, safe='')}/events"
    found = call(db, org, CALENDAR, "GET", url, params=params).json()
    return {"events": [_event(item) for item in found.get("items") or []]}


@tool(
    "google.calendar_create_event",
    description="Create an event on a Google calendar.",
    scope="google:write",
    input_schema={
        "type": "object",
        "properties": {
            "calendar_id": CALENDAR_ID,
            "summary": {"type": "string", "minLength": 1, "maxLength": 500},
            "start": TIME,
            "end": TIME,
            "time_zone": {"type": "string", "maxLength": 64, "description": "IANA name, such as America/Phoenix"},
            "description": {"type": "string", "maxLength": 8000},
            "location": {"type": "string", "maxLength": 500},
        },
        "required": ["summary", "start", "end"],
        "additionalProperties": False,
    },
    confirm=True,
    integration="google",
    available=connected,
)
def calendar_create_event(
    db,
    org,
    caller,
    summary: str,
    start: str,
    end: str,
    calendar_id: str = "primary",
    time_zone: str | None = None,
    description: str | None = None,
    location: str | None = None,
):
    body: dict[str, Any] = {"summary": summary, "start": _when(start), "end": _when(end)}
    if time_zone:
        body["start"]["timeZone"] = body["end"]["timeZone"] = time_zone
    if description:
        body["description"] = description
    if location:
        body["location"] = location
    url = f"{CALENDAR_API}/calendars/{quote(calendar_id, safe='')}/events"
    return _event(call(db, org, CALENDAR, "POST", url, json=body).json())


def _drive_query(text: str) -> str:
    escaped = text.replace("\\", "\\\\").replace("'", "\\'")
    return f"(name contains '{escaped}' or fullText contains '{escaped}') and trashed = false"


@tool(
    "google.drive_search",
    description="Search the Google Drive files the org's Google account can open, by name and content.",
    scope="google:read",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 200},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 50},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    integration="google",
    available=connected,
)
def drive_search(db, org, caller, query: str, max_results: int = 20):
    params = {
        "q": _drive_query(query),
        "pageSize": max_results,
        "fields": "files(id,name,mimeType,modifiedTime,webViewLink)",
        "supportsAllDrives": "true",
        "includeItemsFromAllDrives": "true",
    }
    found = call(db, org, DRIVE_READ, "GET", f"{DRIVE_API}/files", params=params).json()
    return {
        "files": [
            {
                "id": f.get("id"),
                "name": f.get("name"),
                "type": f.get("mimeType"),
                "modified": f.get("modifiedTime"),
                "link": f.get("webViewLink"),
            }
            for f in found.get("files") or []
        ]
    }


@tool(
    "google.drive_read",
    description="The text of a Google Drive file: Docs and Slides as text, Sheets as CSV of the first sheet, "
    "and text files as they are. Other files return only their name and link.",
    scope="google:read",
    input_schema={
        "type": "object",
        "properties": {"file_id": ID},
        "required": ["file_id"],
        "additionalProperties": False,
    },
    integration="google",
    available=connected,
)
def drive_read(db, org, caller, file_id: str):
    url = f"{DRIVE_API}/files/{quote(file_id, safe='')}"
    meta = call(
        db,
        org,
        DRIVE_READ,
        "GET",
        url,
        params={"fields": "id,name,mimeType,size,webViewLink", "supportsAllDrives": "true"},
    ).json()
    kind = str(meta.get("mimeType") or "")
    result = {"id": meta.get("id"), "name": meta.get("name"), "type": kind, "link": meta.get("webViewLink")}
    if kind in EXPORTS:
        response = call(db, org, DRIVE_READ, "GET", f"{url}/export", params={"mimeType": EXPORTS[kind]})
    elif kind.startswith("text/") or kind in ("application/json", "application/xml"):
        if int(meta.get("size") or 0) > MAX_DOWNLOAD_BYTES:
            return {**result, "text": None, "reason": "The file is too large to read"}
        response = call(db, org, DRIVE_READ, "GET", url, params={"alt": "media", "supportsAllDrives": "true"})
    else:
        return {**result, "text": None, "reason": "This file type has no text to read. Open the link"}
    return {**result, **_text(response.content.decode("utf-8", "replace"))}


@tool(
    "google.sheets_read",
    description="Cell values of a Google Sheet. range is A1 notation, such as Sheet1!A1:D50; without it, "
    "the first sheet. Also returns the names of the sheets.",
    scope="google:read",
    input_schema={
        "type": "object",
        "properties": {"spreadsheet_id": ID, "range": {"type": "string", "minLength": 1, "maxLength": 200}},
        "required": ["spreadsheet_id"],
        "additionalProperties": False,
    },
    integration="google",
    available=connected,
)
def sheets_read(db, org, caller, spreadsheet_id: str, range: str | None = None):
    base = f"{SHEETS_API}/{quote(spreadsheet_id, safe='')}"
    meta = call(db, org, SHEETS, "GET", base, params={"fields": "properties.title,sheets.properties.title"}).json()
    names = [s.get("properties", {}).get("title") for s in meta.get("sheets") or []]
    target = range or (f"'{names[0]}'" if names else "A1:Z1000")
    values = call(db, org, SHEETS, "GET", f"{base}/values/{quote(target, safe='')}").json().get("values") or []
    return {
        "title": meta.get("properties", {}).get("title"),
        "sheets": names,
        "range": target,
        "values": values[:MAX_ROWS],
        "truncated": len(values) > MAX_ROWS,
    }


@tool(
    "google.sheets_append",
    description="Add rows after the last row of a Google Sheet. range names the sheet, such as Sheet1. "
    "Values are entered as if typed, so formulas and dates work.",
    scope="google:write",
    input_schema={
        "type": "object",
        "properties": {
            "spreadsheet_id": ID,
            "range": {"type": "string", "minLength": 1, "maxLength": 200},
            "rows": {
                "type": "array",
                "minItems": 1,
                "maxItems": 100,
                "items": {
                    "type": "array",
                    "maxItems": 50,
                    "items": {"type": ["string", "number", "boolean", "null"]},
                },
            },
        },
        "required": ["spreadsheet_id", "range", "rows"],
        "additionalProperties": False,
    },
    confirm=True,
    integration="google",
    available=connected,
)
def sheets_append(db, org, caller, spreadsheet_id: str, range: str, rows: list[list[Any]]):
    url = f"{SHEETS_API}/{quote(spreadsheet_id, safe='')}/values/{quote(range, safe='')}:append"
    params = {"valueInputOption": "USER_ENTERED", "insertDataOption": "INSERT_ROWS"}
    found = call(db, org, SHEETS, "POST", url, params=params, json={"values": rows}).json()
    updates = found.get("updates") or {}
    return {"range": updates.get("updatedRange"), "rows": updates.get("updatedRows")}


def _headers(payload: dict) -> dict[str, str]:
    wanted = {"from", "to", "cc", "subject", "date"}
    return {
        str(h.get("name")).lower(): str(h.get("value"))
        for h in payload.get("headers") or []
        if str(h.get("name")).lower() in wanted
    }


def _plain(payload: dict) -> str:
    """The first text/plain part of a Gmail message, else its first text/html part with the tags kept."""
    found: dict[str, str] = {}
    stack = [payload]
    while stack:
        part = stack.pop(0)
        kind = str(part.get("mimeType") or "")
        data = (part.get("body") or {}).get("data")
        if data and kind in ("text/plain", "text/html") and kind not in found:
            found[kind] = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", "replace")
        stack.extend(part.get("parts") or [])
    return found.get("text/plain") or found.get("text/html") or ""


@tool(
    "google.gmail_search",
    description="Search the mail of the Workspace user that Google acts as. query uses Gmail search, such as "
    "from:dean@asu.edu newer_than:7d. Returns sender, subject, date and a snippet of each message.",
    scope="gmail:read",
    input_schema={
        "type": "object",
        "properties": {
            "query": {"type": "string", "minLength": 1, "maxLength": 500},
            "max_results": {"type": "integer", "minimum": 1, "maximum": 25},
        },
        "required": ["query"],
        "additionalProperties": False,
    },
    integration="google",
    available=delegated,
)
def gmail_search(db, org, caller, query: str, max_results: int = 10):
    found = call(db, org, GMAIL_READ, "GET", f"{GMAIL_API}/messages", params={"q": query, "maxResults": max_results})
    messages = []
    for item in found.json().get("messages") or []:
        message = call(
            db,
            org,
            GMAIL_READ,
            "GET",
            f"{GMAIL_API}/messages/{quote(str(item.get('id')), safe='')}",
            params={"format": "metadata", "metadataHeaders": ["From", "To", "Subject", "Date"]},
        ).json()
        messages.append(
            {"id": message.get("id"), **_headers(message.get("payload") or {}), "snippet": message.get("snippet")}
        )
    return {"messages": messages}


@tool(
    "google.gmail_read",
    description="One message of the Workspace user that Google acts as: headers and the text body.",
    scope="gmail:read",
    input_schema={
        "type": "object",
        "properties": {"message_id": ID},
        "required": ["message_id"],
        "additionalProperties": False,
    },
    integration="google",
    available=delegated,
)
def gmail_read(db, org, caller, message_id: str):
    url = f"{GMAIL_API}/messages/{quote(message_id, safe='')}"
    message = call(db, org, GMAIL_READ, "GET", url, params={"format": "full"}).json()
    payload = message.get("payload") or {}
    return {
        "id": message.get("id"),
        "thread_id": message.get("threadId"),
        **_headers(payload),
        **_text(_plain(payload)),
    }


@tool(
    "google.gmail_send",
    description="Send a plain text email as the Workspace user that Google acts as.",
    scope="gmail:send",
    input_schema={
        "type": "object",
        "properties": {
            "to": {"type": "array", "minItems": 1, "maxItems": 20, "items": {"type": "string", "format": "email"}},
            "cc": {"type": "array", "maxItems": 20, "items": {"type": "string", "format": "email"}},
            "subject": {"type": "string", "minLength": 1, "maxLength": 500},
            "body": {"type": "string", "minLength": 1, "maxLength": 50_000},
        },
        "required": ["to", "subject", "body"],
        "additionalProperties": False,
    },
    confirm=True,
    integration="google",
    available=delegated,
)
def gmail_send(db, org, caller, to: list[str], subject: str, body: str, cc: list[str] | None = None):
    email = EmailMessage()
    email["To"] = ", ".join(to)
    if cc:
        email["Cc"] = ", ".join(cc)
    email["Subject"] = subject
    email.set_content(body)
    raw = base64.urlsafe_b64encode(email.as_bytes()).decode()
    sent = call(db, org, GMAIL_SEND, "POST", f"{GMAIL_API}/messages/send", json={"raw": raw}).json()
    return {"id": sent.get("id"), "thread_id": sent.get("threadId")}
