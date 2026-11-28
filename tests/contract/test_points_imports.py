"""CSV imports of event check-ins: a run row with progress, counts and the error of each failed row."""

import io
import threading

import pytest

from tests.contract.conftest import MEMBER_EMAIL

UPLOAD = "/api/points/soda/uploadEventCSV"
EVENT = "Import check"


def _wait_for_jobs():
    for thread in threading.enumerate():
        if thread.name.startswith("job-") and thread.name != "job-scheduler":
            thread.join(timeout=10)


@pytest.fixture
def cleanup(app):
    yield
    from core.db import db_connect
    from modules.points.models import Points, PointsImport

    with db_connect.SessionLocal() as db:
        db.query(Points).filter_by(event=EVENT).delete()
        db.query(PointsImport).filter_by(event=EVENT).delete()
        db.commit()


def _upload(client, headers, csv_text, points="5"):
    data = {"file": (io.BytesIO(csv_text.encode()), "event.csv"), "event_name": EVENT, "event_points": points}
    return client.post(UPLOAD, data=data, headers=headers, content_type="multipart/form-data")


CSV = (
    "First Name,Last Name,Email,Checked-In Date\n"
    f"Alice,A,{MEMBER_EMAIL},2026-10-01\n"
    "Bob,B,bob@asu.edu,\n"
    "No,Email,,2026-10-01\n"
    f"Alice,A,{MEMBER_EMAIL},2026-10-01\n"
)


def test_an_upload_returns_a_run_that_ends_with_counts_and_row_errors(client, officer_headers, cleanup):
    response = _upload(client, officer_headers, CSV)
    assert response.status_code == 202
    body = response.get_json()
    assert body["message"] == "File is being processed in the background."
    import_id = body["import_id"]
    _wait_for_jobs()

    run = client.get(f"/api/points/soda/imports/{import_id}", headers=officer_headers).get_json()
    assert run["status"] == "done"
    assert run["event"] == EVENT and run["points"] == 5
    assert run["rows_total"] == 3
    assert run["rows_done"] == 3
    assert run["awarded"] == 1
    assert run["skipped"] == 1
    assert run["errors"] == [{"row": 4, "email": None, "message": "The row has no email or no name"}]
    assert run["finished_at"]

    listed = client.get("/api/points/soda/imports", headers=officer_headers).get_json()
    assert listed["imports"][0]["id"] == import_id


@pytest.mark.parametrize("points", ["ten", "", "1.5"])
def test_a_bad_points_value_is_refused(client, officer_headers, points, cleanup):
    response = _upload(client, officer_headers, CSV, points=points)
    assert response.status_code == 400
    assert "event_points" in response.get_json()["error"]


def test_a_run_of_another_org_is_not_found(client, officer_headers, cleanup):
    from core.db import db_connect
    from modules.organizations.models import Organization
    from modules.points.models import PointsImport

    with db_connect.SessionLocal() as db:
        ais = db.query(Organization).filter_by(prefix="ais").one()
        run = PointsImport(organization_id=ais.id, event=EVENT, points=1, status="done")
        db.add(run)
        db.commit()
        run_id = run.id
    assert client.get(f"/api/points/soda/imports/{run_id}", headers=officer_headers).status_code == 404
    assert client.get(f"/api/points/ais/imports/{run_id}", headers=officer_headers).status_code == 200


def test_a_run_cannot_be_queued_twice(app, monkeypatch):
    from core import jobs

    monkeypatch.setattr(jobs, "_running", {"points.import_event_csv:import_id=99"})
    with pytest.raises(jobs.JobBusy):
        jobs.defer(
            "points.import_event_csv",
            file_content="",
            event_name=EVENT,
            event_points=1,
            org_prefix="soda",
            import_id=99,
        )


def test_a_job_queued_before_the_runs_existed_still_runs(app, cleanup):
    from core.db import db_connect
    from modules.points.models import Points
    from modules.points.submodules.checkins import jobs

    jobs.import_event_csv(CSV, EVENT, 2, "soda")
    with db_connect.SessionLocal() as db:
        assert db.query(Points).filter_by(event=EVENT).count() == 1


def test_the_imports_tool_lists_the_runs(client, officer_headers, cleanup):
    from tests.contract.test_officer_tools import _issue, _result

    import_id = _upload(client, officer_headers, CSV).get_json()["import_id"]
    _wait_for_jobs()
    runs = _result(client, _issue("members:read"), "points.imports")["imports"]
    run = next(r for r in runs if r["id"] == import_id)
    assert run["status"] == "done" and run["awarded"] == 1 and len(run["errors"]) == 1
