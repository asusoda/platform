"""Event attendance CSV import. No Flask here."""

import csv
from io import StringIO

from core.db import db_connect
from core.log import get_logger
from modules.organizations import service as organizations
from modules.points.models import Points
from modules.users.models import User
from modules.users.service import manage_user_in_organization

logger = get_logger(__name__)


def process_csv_in_background(file_content, event_name, event_points, org_prefix):
    """Award event_points to each checked-in row of the CSV, once per email. Creates missing members."""
    csv_reader = csv.DictReader(StringIO(file_content))

    db = next(db_connect.get_db())
    success_count = 0
    errors = []
    processed_emails = set()

    try:
        organization = organizations.find_by_prefix(db, org_prefix, active_only=True)

        if not organization:
            errors.append(f"Organization {org_prefix} not found")
            return

        for row in csv_reader:
            if not row.get("Checked-In Date"):
                continue

            email = row.get("Email")
            first_name = row.get("First Name", "")
            last_name = row.get("Last Name", "")
            name = f"{first_name} {last_name}".strip()

            if not email or not name:
                errors.append(f"Missing required fields (Email, Name) in row: {row}")
                continue

            if email in processed_emails:
                continue

            user = db.query(User).filter_by(email=email).first()

            if not user:
                user_data = {"email": email, "name": name, "student_id": None, "class_standing": "N/A", "major": "N/A"}
                user, success, message = manage_user_in_organization(db, organization.id, user_data)
                if not success:
                    errors.append(f"Failed to create user {email}: {message}")
                    continue

            point = Points(
                points=event_points,
                event=event_name,
                awarded_by_officer="CSV Upload",
                user_id=user.id,
                organization_id=organization.id,
            )
            db.add(point)
            db.commit()

            processed_emails.add(email)
            success_count += 1

    except Exception as e:
        errors.append(f"An unexpected error occurred: {str(e)}")
    finally:
        db.close()

    logger.info(
        f"CSV processing finished for org '{org_prefix}'. Awarded points to {success_count} users. Errors: {len(errors)}"
    )
    if errors:
        logger.warning(f"Errors encountered: {errors}")
