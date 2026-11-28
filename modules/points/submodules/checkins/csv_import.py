"""Event attendance CSV imports: the run row, the parse and the award in batches. No Flask here."""

import csv
from datetime import UTC, datetime
from io import StringIO

from core import jobs
from core.cache import publish
from core.db import db_connect
from core.log import get_logger
from modules.members.models import User, UserOrganizationMembership
from modules.members.service import manage_user_in_organization
from modules.organizations import service as organizations
from modules.points.models import Points, PointsImport

logger = get_logger(__name__)

BATCH_ROWS = 25  # checked-in rows in one commit
MAX_ERRORS = 200  # errors kept on one run
KEEP_RUNS = 50  # runs kept for each org
CHECKED_IN = "Checked-In Date"
CSV_UPLOAD = "CSV Upload"


def changed(org_prefix: str) -> None:
    """Drop the cached reads of the org in every process, so new totals show at the next read."""
    publish("org", org_prefix)


def checked_in_rows(file_content: str) -> list[tuple[int, dict]]:
    """The (CSV line number, row) of each row with a check-in date. The header is line 1."""
    reader = csv.DictReader(StringIO(file_content))
    return [(number, row) for number, row in enumerate(reader, start=2) if row.get(CHECKED_IN)]


def run_json(run: PointsImport) -> dict:
    """An import run as the routes and tools return it."""
    return {
        "id": run.id,
        "event": run.event,
        "points": run.points,
        "status": run.status,
        "rows_total": run.rows_total,
        "rows_done": run.rows_done,
        "awarded": run.awarded,
        "skipped": run.skipped,
        "errors": list(run.errors or []),
        "created_by": run.created_by,
        "created_at": run.created_at.isoformat() if run.created_at else None,
        "finished_at": run.finished_at.isoformat() if run.finished_at else None,
    }


def queue(db, org, file_content: str, event: str, points: int, created_by: str | None) -> PointsImport:
    """Add a queued run, keep the newest KEEP_RUNS of the org, and defer the import job. Commits."""
    run = PointsImport(
        organization_id=org.id,
        event=event,
        points=points,
        status="queued",
        rows_total=len(checked_in_rows(file_content)),
        errors=[],
        created_by=created_by,
    )
    db.add(run)
    db.flush()
    old = (
        db.query(PointsImport.id)
        .filter(PointsImport.organization_id == org.id)
        .order_by(PointsImport.id.desc())
        .offset(KEEP_RUNS)
        .all()
    )
    if old:
        db.query(PointsImport).filter(PointsImport.id.in_([row.id for row in old])).delete(synchronize_session=False)
    db.commit()
    logger.info("csv import queued org=%s import_id=%s event=%r rows=%s", org.prefix, run.id, event, run.rows_total)
    try:
        jobs.defer(
            "points.import_event_csv",
            file_content=file_content,
            event_name=event,
            event_points=points,
            org_prefix=org.prefix,
            import_id=run.id,
        )
    except Exception:
        logger.exception("csv import could not be queued org=%s import_id=%s", org.prefix, run.id)
        run.status = "failed"
        run.finished_at = datetime.now(UTC)
        db.commit()
        raise
    return run


def runs(db, organization_id, limit: int = 20) -> list[dict]:
    """The org's newest import runs."""
    rows = (
        db.query(PointsImport)
        .filter(PointsImport.organization_id == organization_id)
        .order_by(PointsImport.id.desc())
        .limit(limit)
        .all()
    )
    return [run_json(row) for row in rows]


def run(db, organization_id, import_id: int) -> PointsImport | None:
    """The org's import run with this id, or None. A run of another org is None."""
    return db.query(PointsImport).filter_by(id=import_id, organization_id=organization_id).first()


def _has_membership(db, user_id, organization_id) -> bool:
    """True if the user has a membership row in the org, active or not."""
    query = db.query(UserOrganizationMembership.id).filter_by(user_id=user_id, organization_id=organization_id)
    return query.first() is not None


def _member(db, organization_id, email: str, name: str) -> tuple[User | None, str | None]:
    """The user with this email, made a member of the org when needed, or (None, the reason it failed)."""
    user = db.query(User).filter_by(email=email).first()
    if not user:
        user_data = {"email": email, "name": name, "student_id": None, "class_standing": "N/A", "major": "N/A"}
        user, success, message = manage_user_in_organization(db, organization_id, user_data)
        if not success or user is None:
            return None, f"Could not add the member: {message}"
    elif not _has_membership(db, user.id, organization_id):
        joined, success, message = manage_user_in_organization(db, organization_id, {"email": email})
        if not success or joined is None:
            return None, f"Could not add the user to the org: {message}"
        user = joined
    return user, None


class _Progress:
    """The counts of one import, written to its run row (when there is one) after each batch."""

    def __init__(self, db, run_row: PointsImport | None) -> None:
        self.db = db
        self.run = run_row
        self.rows_done = 0
        self.awarded = 0
        self.skipped = 0
        self.line = 0
        self.errors: list[dict] = []
        self._committed = (0, 0, 0, 0)

    def error(self, row: int, email: str | None, message: str) -> None:
        if len(self.errors) < MAX_ERRORS:
            self.errors.append({"row": row, "email": email, "message": message})

    def save(self, status: str | None = None) -> None:
        if self.run is not None:
            self.run.rows_done = self.rows_done
            self.run.awarded = self.awarded
            self.run.skipped = self.skipped
            self.run.errors = list(self.errors)
            if status is not None:
                self.run.status = status
                if status in ("done", "failed"):
                    self.run.finished_at = datetime.now(UTC)
        self.db.commit()
        self._committed = (self.rows_done, self.awarded, self.skipped, len(self.errors))

    def rollback(self) -> None:
        """Undo the batch that did not commit, in the database and in the counts."""
        self.db.rollback()
        self.rows_done, self.awarded, self.skipped, errors = self._committed
        del self.errors[errors:]


def process_csv_in_background(file_content, event_name, event_points, org_prefix, import_id: int | None = None):
    """Award event_points to each checked-in row of the CSV, once per email, BATCH_ROWS rows per commit.

    Creates missing users and memberships. With import_id, the run row gets the progress and the error
    of each failed row; a job queued without one (before the runs existed) only logs the counts.
    """
    db = db_connect.SessionLocal()
    progress = _Progress(db, None)
    try:
        organization = organizations.find_by_prefix(db, org_prefix, active_only=True)
        if not organization:
            logger.warning("csv import skipped org=%s import_id=%s reason=org not found", org_prefix, import_id)
            return
        progress.run = run(db, organization.id, import_id) if import_id is not None else None
        rows = checked_in_rows(file_content)
        if progress.run is not None:
            progress.run.rows_total = len(rows)
        progress.save("running")

        seen: set[str] = set()
        for index, (number, row) in enumerate(rows, start=1):
            progress.line = number
            email = (row.get("Email") or "").strip()
            name = f"{row.get('First Name', '')} {row.get('Last Name', '')}".strip()
            if not email or not name:
                progress.error(number, email or None, "The row has no email or no name")
            elif email.lower() in seen:
                progress.skipped += 1
            else:
                user, problem = _member(db, organization.id, email, name)
                if user is None:
                    progress.error(number, email, problem or "Could not add the member")
                else:
                    db.add(
                        Points(
                            points=event_points,
                            event=event_name,
                            awarded_by_officer=CSV_UPLOAD,
                            user_id=user.id,
                            organization_id=organization.id,
                        )
                    )
                    seen.add(email.lower())
                    progress.awarded += 1
            progress.rows_done = index
            if index % BATCH_ROWS == 0:
                progress.save()
                changed(org_prefix)
        progress.save("done")
    except Exception:
        logger.exception(
            "csv import failed org=%s import_id=%s rows_done=%s", org_prefix, import_id, progress.rows_done
        )
        progress.rollback()
        if progress.run is not None:
            progress.error(progress.line, None, "The import stopped on an unexpected error in this batch")
            progress.save("failed")
        raise
    finally:
        changed(org_prefix)
        db.close()
        logger.info(
            "csv import finished org=%s import_id=%s awarded=%s skipped=%s errors=%s",
            org_prefix,
            import_id,
            progress.awarded,
            progress.skipped,
            len(progress.errors),
        )
