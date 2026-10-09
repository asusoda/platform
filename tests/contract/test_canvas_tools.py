"""The canvas.* tools: each reads Canvas with the named member's own grant. A fake Canvas answers every call."""

import datetime
import logging
import random
from collections.abc import Callable

import pytest
from cryptography.fernet import Fernet

from core.db import db_connect
from modules.accounts import canvas, providers, service
from modules.accounts.models import AccountGrant

CANVAS = "https://canvas.test"
API = f"{CANVAS}/api/v1/"
TOOLS = [
    "canvas.announcements",
    "canvas.assignment_grades",
    "canvas.assignments",
    "canvas.calendar",
    "canvas.courses",
    "canvas.grades",
]


class FakeResponse:
    def __init__(self, status_code, body, link=""):
        self.status_code = status_code
        self._body = body
        self.headers = {"Link": link} if link else {}

    def json(self):
        return self._body


class FakeCanvas:
    """Answers GETs by the path after /api/v1/. A list value is a sequence of pages."""

    def __init__(self):
        self.pages: dict[str, FakeResponse | Callable[[str], FakeResponse]] = {}
        self.calls: list[tuple[str, list | None, str]] = []

    def get(self, url, params=None, headers=None, timeout=None):
        assert timeout is not None and headers is not None
        self.calls.append((url, params, headers["Authorization"]))
        path = url.split("?", 1)[0].removeprefix(API)
        answer = self.pages.get(path)
        if answer is None:
            return FakeResponse(404, {})
        if isinstance(answer, FakeResponse):
            return answer
        return answer(url)

    def tokens(self):
        return {auth for _, _, auth in self.calls}


class FakeTokenEndpoint:
    def __init__(self):
        self.responses = []

    def post(self, url, data=None, timeout=None):
        return self.responses.pop(0)


@pytest.fixture(autouse=True)
def configured(monkeypatch):
    monkeypatch.setenv("SECRETS_KEY", Fernet.generate_key().decode())
    monkeypatch.setenv("ACCOUNTS_BASE_URL", "https://api.test")
    monkeypatch.setenv("ACCOUNTS_CANVAS_CLIENT_ID", "canvas-id")
    monkeypatch.setenv("ACCOUNTS_CANVAS_CLIENT_SECRET", "canvas-secret")
    monkeypatch.setenv("ACCOUNTS_CANVAS_URL", CANVAS)


@pytest.fixture
def fake(monkeypatch):
    found = FakeCanvas()
    monkeypatch.setattr(canvas.requests, "get", found.get)
    return found


@pytest.fixture
def endpoint(monkeypatch):
    found = FakeTokenEndpoint()
    monkeypatch.setattr(providers.requests, "post", found.post)
    return found


def _org_id(prefix):
    from modules.organizations.models import Organization

    db = db_connect.SessionLocal()
    try:
        return db.query(Organization.id).filter_by(prefix=prefix).scalar()
    finally:
        db.close()


def _issue(prefix, *scopes):
    from modules.auth import machine_tokens

    db = db_connect.SessionLocal()
    try:
        value, _ = machine_tokens.issue(
            db, organization_id=_org_id(prefix), name="canvas-agent", kind="agent", scopes=list(scopes)
        )
        return {"Authorization": f"Bearer {value}"}
    finally:
        db.close()


@pytest.fixture
def agent(app):
    return _issue("soda", "canvas:read")


@pytest.fixture
def grants(app):
    """Saves a Canvas grant for a member. Removes every grant it saved after the test."""
    saved: list[str] = []

    def connect(discord_id, access, prefix="soda", expires_in=3600):
        db = db_connect.SessionLocal()
        try:
            expires_at = datetime.datetime.now(datetime.UTC).replace(tzinfo=None) + datetime.timedelta(
                seconds=expires_in
            )
            tokens = providers.Tokens(access, "rt-" + access, "url:GET|/api/v1/courses", expires_at)
            service._save(db, _org_id(prefix), discord_id, "canvas", tokens)
        finally:
            db.close()
        saved.append(discord_id)

    yield connect
    db = db_connect.SessionLocal()
    try:
        db.query(AccountGrant).filter(AccountGrant.discord_id.in_(saved)).delete(synchronize_session=False)
        db.commit()
    finally:
        db.close()


def _member_id():
    return str(random.randint(10**17, 10**18))


def _names(client, headers):
    return [t["name"] for t in client.get("/api/tools", headers=headers).get_json()["tools"] if t["name"] in TOOLS]


def _call(client, headers, name, discord_id):
    return client.post(f"/api/tools/{name}", json={"discord_id": discord_id}, headers=headers)


COURSES = [
    {"id": 101, "name": "Data Structures", "course_code": "CSE 310"},
    {"id": 102, "name": "Linear Algebra", "course_code": "MAT 343"},
]


def _fill(fake):
    fake.pages["courses"] = lambda url: FakeResponse(
        200,
        [
            {
                **c,
                "enrollments": [
                    {"type": "student", "computed_current_score": 93.5, "computed_current_grade": "A"},
                ],
            }
            for c in COURSES
        ],
    )
    fake.pages["users/self/todo"] = FakeResponse(
        200,
        [
            {
                "type": "submitting",
                "context_name": "Linear Algebra",
                "assignment": {"name": "HW 4", "due_at": "2026-10-20T06:59:00Z", "points_possible": 10.0},
            },
            {
                "type": "submitting",
                "context_name": "Data Structures",
                "assignment": {
                    "name": "Project 2",
                    "due_at": "2026-10-12T06:59:00Z",
                    "points_possible": 50,
                    "html_url": f"{CANVAS}/courses/101/assignments/9",
                },
            },
            {"type": "grading", "context_name": "Data Structures", "assignment": {"name": "Not mine"}},
        ],
    )
    fake.pages["announcements"] = FakeResponse(
        200,
        [
            {
                "title": "Exam room",
                "message": "<p>The exam is in   <b>COOR 170</b>.</p>",
                "posted_at": "2026-10-08T15:00:00Z",
                "context_code": "course_102",
                "html_url": f"{CANVAS}/courses/102/discussion_topics/5",
            }
        ],
    )
    fake.pages["users/self/upcoming_events"] = FakeResponse(
        200, [{"title": "Office hours", "start_at": "2026-10-10T17:00:00Z", "location_name": "BYENG 210"}]
    )
    fake.pages["courses/101/assignments"] = FakeResponse(
        200,
        [
            {"name": "Project 1", "points_possible": 50, "submission": {"score": 45.0, "grade": "45"}},
            {"name": "Project 2", "points_possible": 50, "submission": {"score": None, "grade": None}},
        ],
    )
    fake.pages["courses/102/assignments"] = FakeResponse(
        200, [{"name": "HW 1", "points_possible": 10, "submission": {"score": 9.5, "grade": "A"}}]
    )


def test_each_tool_returns_its_shape(client, agent, fake, grants, caplog):
    caplog.set_level(logging.DEBUG)
    discord_id = _member_id()
    grants(discord_id, "at-member")
    _fill(fake)
    assert _names(client, agent) == TOOLS

    def result(name):
        response = _call(client, agent, name, discord_id)
        assert response.status_code == 200, response.get_json()
        return response.get_json()["result"]

    courses = result("canvas.courses")
    assert courses["courses"] == [
        {"id": 101, "name": "Data Structures", "code": "CSE 310"},
        {"id": 102, "name": "Linear Algebra", "code": "MAT 343"},
    ]
    assert courses["text"] == "2 active courses:\n- Data Structures (CSE 310)\n- Linear Algebra (MAT 343)"

    assignments = result("canvas.assignments")
    assert [a["name"] for a in assignments["assignments"]] == ["Project 2", "HW 4"]
    assert assignments["assignments"][0] == {
        "name": "Project 2",
        "course": "Data Structures",
        "due_at": "2026-10-12T06:59:00Z",
        "points": 50.0,
        "url": f"{CANVAS}/courses/101/assignments/9",
    }
    assert "- Project 2 (Data Structures) due Oct 12, 2026 06:59 UTC, 50 pts https://" in assignments["text"]

    grades = result("canvas.grades")
    assert grades["grades"][0] == {"course": "Data Structures", "score": 93.5, "grade": "A"}
    assert grades["text"].startswith("Current grades:\n- Data Structures: A (93.5)")

    announcements = result("canvas.announcements")
    assert announcements["announcements"] == [
        {
            "title": "Exam room",
            "course": "Linear Algebra",
            "posted_at": "2026-10-08T15:00:00Z",
            "body": "The exam is in COOR 170.",
            "url": f"{CANVAS}/courses/102/discussion_topics/5",
        }
    ]
    sent = next(params for url, params, _ in fake.calls if url == API + "announcements")
    assert ("context_codes[]", "course_101") in sent and ("context_codes[]", "course_102") in sent

    events = result("canvas.calendar")
    assert events["events"] == [
        {"title": "Office hours", "start_at": "2026-10-10T17:00:00Z", "location": "BYENG 210", "url": None}
    ]
    assert events["text"] == "1 upcoming events:\n- Office hours Oct 10, 2026 17:00 UTC at BYENG 210"

    graded = result("canvas.assignment_grades")
    assert graded["grades"] == [
        {"course": "Data Structures", "name": "Project 1", "score": 45.0, "points": 50.0, "grade": "45"},
        {"course": "Linear Algebra", "name": "HW 1", "score": 9.5, "points": 10.0, "grade": "A"},
    ]
    assert (
        graded["text"]
        == "Assignment grades:\n- Project 1 (Data Structures): 45 (45/50)\n- HW 1 (Linear Algebra): A (9.5/10)"
    )

    assert fake.tokens() == {"Bearer at-member"}
    assert all(url.startswith(API) for url, _, _ in fake.calls)
    logged = caplog.text
    for secret in ("at-member", "93.5", "Data Structures", "COOR 170"):
        assert secret not in logged


def test_only_the_named_members_grant_is_used(client, agent, fake, grants):
    alice, bob = _member_id(), _member_id()
    grants(bob, "at-bob")
    _fill(fake)

    refused = _call(client, agent, "canvas.grades", alice)
    assert refused.status_code == 409
    assert "has not connected Canvas" in refused.get_json()["error"]
    assert "/api/accounts/members/<discord_id>/canvas/login" in refused.get_json()["error"]
    assert fake.calls == []

    grants(alice, "at-alice")
    assert _call(client, agent, "canvas.grades", alice).status_code == 200
    assert fake.tokens() == {"Bearer at-alice"}


def test_a_grant_in_another_org_is_not_used(client, fake, grants):
    discord_id = _member_id()
    grants(discord_id, "at-soda", prefix="soda")
    _fill(fake)
    other = _issue("ais", "canvas:read")
    assert _call(client, other, "canvas.courses", discord_id).status_code == 409
    assert fake.calls == []


def test_expired_token_is_refreshed_first(client, agent, fake, grants, endpoint):
    discord_id = _member_id()
    grants(discord_id, "at-old", expires_in=-60)
    _fill(fake)
    endpoint.responses.append(FakeResponse(200, {"access_token": "at-new", "expires_in": 3600}))
    assert _call(client, agent, "canvas.courses", discord_id).status_code == 200
    assert fake.tokens() == {"Bearer at-new"}


def test_refresh_failures_are_clear_errors(client, agent, fake, grants, endpoint):
    outage, revoked = _member_id(), _member_id()
    grants(outage, "at-outage", expires_in=-60)
    grants(revoked, "at-revoked", expires_in=-60)

    endpoint.responses.append(FakeResponse(503, {}))
    failed = _call(client, agent, "canvas.courses", outage)
    assert failed.status_code == 502 and "could not refresh" in failed.get_json()["error"]

    endpoint.responses.append(FakeResponse(400, {"error": "invalid_grant"}))
    expired = _call(client, agent, "canvas.courses", revoked)
    assert expired.status_code == 409 and "connection expired" in expired.get_json()["error"]
    assert fake.calls == []


def test_canvas_refusing_the_token_is_a_clear_error(client, agent, fake, grants):
    discord_id = _member_id()
    grants(discord_id, "at-member")
    fake.pages["courses"] = FakeResponse(401, {"errors": [{"message": "Invalid access token."}]})
    refused = _call(client, agent, "canvas.courses", discord_id)
    assert refused.status_code == 409 and "rejected the member's token" in refused.get_json()["error"]


def test_tools_need_the_canvas_scope(client, fake, grants):
    discord_id = _member_id()
    grants(discord_id, "at-member")
    _fill(fake)
    headers = _issue("soda", "accounts:token", "accounts:link")
    assert _names(client, headers) == []
    assert _call(client, headers, "canvas.courses", discord_id).status_code == 404
    assert fake.calls == []


def test_tools_hide_when_canvas_is_off(client, agent, fake, grants, monkeypatch):
    discord_id = _member_id()
    grants(discord_id, "at-member")
    monkeypatch.delenv("ACCOUNTS_CANVAS_CLIENT_ID")
    assert _names(client, agent) == []
    assert _call(client, agent, "canvas.courses", discord_id).status_code == 404
    assert fake.calls == []


def test_discord_id_is_validated(client, agent):
    assert _call(client, agent, "canvas.courses", "not-a-number").status_code == 400
    assert client.post("/api/tools/canvas.courses", json={}, headers=agent).status_code == 400


def test_pages_stop_at_the_cap_and_stay_on_canvas(client, agent, fake, grants):
    discord_id = _member_id()
    grants(discord_id, "at-member")

    def todo_page(url):
        page = int(url.rsplit("page=", 1)[1]) if "page=" in url else 1
        items = [{"type": "submitting", "context_name": "C", "assignment": {"name": f"A{page}-{i}"}} for i in range(3)]
        return FakeResponse(200, items, link=f'<{API}users/self/todo?page={page + 1}&per_page=20>; rel="next"')

    fake.pages["users/self/todo"] = todo_page
    result = _call(client, agent, "canvas.assignments", discord_id).get_json()["result"]
    assert len(fake.calls) == canvas.MAX_PAGES
    assert len(result["assignments"]) == 3 * canvas.MAX_PAGES

    fake.calls.clear()
    fake.pages["courses"] = FakeResponse(
        200, COURSES, link='<https://elsewhere.test/api/v1/courses?page=2>; rel="next"'
    )
    assert _call(client, agent, "canvas.courses", discord_id).status_code == 200
    assert [url for url, _, _ in fake.calls] == [API + "courses"]


def test_results_are_capped(client, agent, fake, grants):
    discord_id = _member_id()
    grants(discord_id, "at-member")
    many = [{"id": i, "name": f"Course {i}", "course_code": f"C{i}"} for i in range(1, 40)]
    fake.pages["courses"] = FakeResponse(200, many, link=f'<{API}courses?page=2>; rel="next"')
    result = _call(client, agent, "canvas.courses", discord_id).get_json()["result"]
    assert len(result["courses"]) == canvas.MAX_ITEMS
    assert len(fake.calls) == 1
