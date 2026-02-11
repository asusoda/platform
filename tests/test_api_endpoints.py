import os
import time

import pytest
import requests

pytestmark = pytest.mark.skipif(
    not all(os.environ.get(v) for v in ("BASE_URL", "TEST_TOKEN")),
    reason="API integration tests require BASE_URL and TEST_TOKEN environment variables",
)

# --- Configuration ---
BASE_URL = os.environ.get("BASE_URL", "http://127.0.0.1:8000")
TEST_TOKEN = os.environ.get("TEST_TOKEN", "")  # nosec B105

DEFAULT_HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {TEST_TOKEN}"}

NO_AUTH_HEADERS = {"Content-Type": "application/json"}


# --- Helper Function ---
def make_request(method, endpoint, headers=None, params=None, data=None, description=""):
    url = f"{BASE_URL}{endpoint}"
    print(f"--- Testing: {description} ({method.upper()} {endpoint}) ---")

    response = requests.request(
        method,
        url,
        headers=headers,
        params=params,
        json=data if isinstance(data, dict) else None,
        data=data if not isinstance(data, dict) else None,
        timeout=10,
    )

    if "error" in description.lower() or "invalid" in description.lower() or "unauthorized" in description.lower():
        assert response.status_code >= 400, f"Expected error status code (>=400), got {response.status_code}"
    elif endpoint == "/auth/login":
        assert response.status_code in (200, 302), f"Expected 200 or 302 for /auth/login, got {response.status_code}"
    else:
        assert response.status_code < 400, f"Expected success status code (<400), got {response.status_code}"

    time.sleep(0.05)


# --- Test Functions for Each Module ---


def test_health_endpoint():
    print("\n========== Testing Health Endpoint ==========")
    make_request(
        "GET", "/health", headers=NO_AUTH_HEADERS, description="Health Check - Includes commit hash and started_at"
    )


def test_auth_endpoints():
    print("\n========== Testing Auth Endpoints ==========")
    make_request("GET", "/auth/login", headers=NO_AUTH_HEADERS, description="Auth Login Redirect")

    # /validToken - This is a typo in your backend (should be /validateToken or similar based on usage)
    # Assuming it's /validateToken as defined later
    # make_request("GET", "/auth/validToken", headers=DEFAULT_HEADERS, description="Auth Valid Token (Corrected to /validateToken below)")

    make_request(
        "GET",
        "/auth/callback",
        headers=NO_AUTH_HEADERS,
        params={"code": "test_auth_code"},
        description="Auth Callback with code",
    )
    make_request(
        "GET", "/auth/callback", headers=NO_AUTH_HEADERS, description="Auth Callback without code (expect error)"
    )

    make_request("GET", "/auth/validateToken", headers=DEFAULT_HEADERS, description="Auth Validate Token - Valid Token")
    make_request(
        "GET",
        "/auth/validateToken",
        headers={"Authorization": "Bearer INVALID_TOKEN", "Content-Type": "application/json"},
        description="Auth Validate Token - Invalid Token (expect error)",
    )
    # Test for expired token would require a way to generate/get an expired one

    make_request(
        "GET",
        "/auth/refresh",
        headers=DEFAULT_HEADERS,
        description="Auth Refresh Token (assuming token is not expired)",
    )
    # Test with an expired token would require specific setup

    make_request(
        "GET",
        "/auth/appToken",
        headers=DEFAULT_HEADERS,
        params={"appname": "test_app"},
        description="Auth Generate App Token",
    )
    make_request(
        "GET",
        "/auth/appToken",
        headers=DEFAULT_HEADERS,
        description="Auth Generate App Token - Missing appname (expect error)",
    )

    make_request("GET", "/auth/name", headers=DEFAULT_HEADERS, description="Auth Get Name")
    make_request("GET", "/auth/logout", headers=DEFAULT_HEADERS, description="Auth Logout")
    make_request("GET", "/auth/success", headers=NO_AUTH_HEADERS, description="Auth Success Page")


def test_points_endpoints():
    print("\n========== Testing Points Endpoints ==========")
    make_request(
        "GET", "/points/", headers=NO_AUTH_HEADERS, description="Points Index"
    )  # Assuming no auth, adjust if needed

    user_data_good = {
        "email": f"testuser_{int(time.time())}@example.com",
        "asu_id": "1234567890",
        "name": "Test User",
        "academic_standing": "Senior",
        "major": "CS",
    }
    make_request(
        "POST", "/points/add_user", headers=DEFAULT_HEADERS, data=user_data_good, description="Points Add User - New"
    )
    make_request(
        "POST",
        "/points/add_user",
        headers=DEFAULT_HEADERS,
        data=user_data_good,
        description="Points Add User - Duplicate (expect error/specific code)",
    )  # Test duplicate

    points_data = {
        "user_email": user_data_good["email"],
        "points": 10,
        "event": "Test Event",
        "awarded_by_officer": "Test Officer",
    }
    make_request(
        "POST",
        "/points/add_points",
        headers=DEFAULT_HEADERS,
        data=points_data,
        description="Points Add Points - Existing User",
    )
    make_request(
        "POST",
        "/points/add_points",
        headers=DEFAULT_HEADERS,
        data={
            "user_email": "nonexistent@example.com",
            "points": 5,
            "event": "Another Event",
            "awarded_by_officer": "Test Officer",
        },
        description="Points Add Points - Non-existent User (expect error)",
    )

    make_request("GET", "/points/get_users", headers=DEFAULT_HEADERS, description="Points Get Users")
    make_request("GET", "/points/get_points", headers=DEFAULT_HEADERS, description="Points Get Points")

    make_request("GET", "/points/leaderboard", headers=NO_AUTH_HEADERS, description="Points Leaderboard - No Auth")
    make_request(
        "GET",
        "/points/leaderboard",
        headers=DEFAULT_HEADERS,
        description="Points Leaderboard - With Auth (shows email)",
    )

    # File upload is complex for a simple script, sending minimal form data
    # make_request("POST", "/points/uploadEventCSV", headers={"Authorization": f"Bearer {TEST_TOKEN}"}, data=form_data_csv, description="Points Upload Event CSV (Simplified - no actual file)")
    print("Skipping /points/uploadEventCSV test as it requires actual file upload.")

    make_request(
        "GET",
        "/points/getUserPoints",
        headers=DEFAULT_HEADERS,
        params={"email": user_data_good["email"]},
        description="Points Get User Points - Existing User",
    )
    make_request(
        "GET",
        "/points/getUserPoints",
        headers=DEFAULT_HEADERS,
        params={"email": "nonexistent@example.com"},
        description="Points Get User Points - Non-existent User (expect error)",
    )

    assign_points_data = {
        "user_identifier": user_data_good["email"],
        "points": 5,
        "event": "Assigned Event",
        "awarded_by_officer": "Admin",
    }
    make_request(
        "POST",
        "/points/assignPoints",
        headers=DEFAULT_HEADERS,
        data=assign_points_data,
        description="Points Assign Points",
    )

    delete_points_data = {
        "user_email": user_data_good["email"],
        "event": "Test Event",
    }  # Assuming "Test Event" was added
    make_request(
        "DELETE",
        "/points/delete_points",
        headers=DEFAULT_HEADERS,
        data=delete_points_data,
        description="Points Delete Points by Event",
    )


def test_public_endpoints():
    print("\n========== Testing Public Endpoints ==========")
    # /getnextevent seems to be a stub in modules/public/api.py
    make_request("GET", "/public/getnextevent", headers=NO_AUTH_HEADERS, description="Public Get Next Event")

    # This leaderboard is different from /points/leaderboard
    make_request("GET", "/public/leaderboard", headers=NO_AUTH_HEADERS, description="Public Leaderboard")

    # Test serving static files (index.html)
    make_request("GET", "/", headers=NO_AUTH_HEADERS, description="Public Serve Static - Root (index.html)")
    # make_request("GET", "/manifest.json", headers=NO_AUTH_HEADERS, description="Public Serve Static - manifest.json") # Example


def test_calendar_endpoints():
    print("\n========== Testing Calendar Endpoints (including OCP) ==========")
    make_request(
        "POST", "/calendar/notion-webhook", headers=NO_AUTH_HEADERS, data={}, description="Calendar Notion Webhook"
    )
    make_request("GET", "/calendar/events", headers=NO_AUTH_HEADERS, description="Calendar Get Events for Frontend")

    if os.environ.get("ALLOW_DESTRUCTIVE_TESTS", "").lower() == "true":
        make_request(
            "POST",
            "/calendar/delete-all-events",
            headers=NO_AUTH_HEADERS,
            data={},
            description="Calendar Delete All Events (Potentially Destructive - expect error if not configured/allowed)",
        )
    else:
        print("Skipping /calendar/delete-all-events (set ALLOW_DESTRUCTIVE_TESTS=true to enable)")

    # OCP Endpoints (prefixed with /ocp)
    ocp_prefix = "/ocp"
    make_request(
        "POST", f"{ocp_prefix}/sync-from-notion", headers=NO_AUTH_HEADERS, data={}, description="OCP Sync from Notion"
    )
    make_request(
        "POST",
        f"{ocp_prefix}/debug-sync-from-notion",
        headers=NO_AUTH_HEADERS,
        data={},
        description="OCP Debug Sync from Notion",
    )
    make_request(
        "GET",
        f"{ocp_prefix}/diagnose-unknown-officers",
        headers=NO_AUTH_HEADERS,
        description="OCP Diagnose Unknown Officers (GET)",
    )
    make_request(
        "POST",
        f"{ocp_prefix}/diagnose-unknown-officers",
        headers=NO_AUTH_HEADERS,
        data={},
        description="OCP Diagnose Unknown Officers (POST)",
    )
    make_request("GET", f"{ocp_prefix}/officers", headers=NO_AUTH_HEADERS, description="OCP Get Officer Leaderboard")

    test_officer_email = "testofficer@example.com"  # Use an email that might exist or not for testing
    make_request(
        "GET",
        f"{ocp_prefix}/officer/{test_officer_email}/contributions",
        headers=NO_AUTH_HEADERS,
        description="OCP Get Officer Contributions",
    )

    add_contrib_data = {
        "email": test_officer_email,
        "name": "Test Officer OCP",
        "event": "OCP Event",
        "points": 2,
        "role": "Participant",
    }
    make_request(
        "POST",
        f"{ocp_prefix}/add-contribution",
        headers=NO_AUTH_HEADERS,
        data=add_contrib_data,
        description="OCP Add Contribution",
    )

    # For update/delete, you'd need a valid point_id from a previously created contribution
    test_point_id = 1  # Replace with a real ID from your DB after an add
    update_contrib_data = {"points": 3, "event": "Updated OCP Event"}
    make_request(
        "PUT",
        f"{ocp_prefix}/contribution/{test_point_id}",
        headers=NO_AUTH_HEADERS,
        data=update_contrib_data,
        description=f"OCP Update Contribution ID {test_point_id} (ensure ID exists)",
    )
    make_request(
        "DELETE",
        f"{ocp_prefix}/contribution/{test_point_id}",
        headers=NO_AUTH_HEADERS,
        description=f"OCP Delete Contribution ID {test_point_id} (ensure ID exists)",
    )

    test_officer_id_ocp = "some_officer_uuid_or_email"  # Use a valid identifier for an officer
    make_request(
        "GET",
        f"{ocp_prefix}/officer/{test_officer_id_ocp}",
        headers=NO_AUTH_HEADERS,
        description="OCP Get Officer Details",
    )
    make_request("GET", f"{ocp_prefix}/events", headers=NO_AUTH_HEADERS, description="OCP Get All Contribution Events")
    make_request(
        "POST",
        f"{ocp_prefix}/repair-unknown-officers",
        headers=NO_AUTH_HEADERS,
        data={},
        description="OCP Repair Unknown Officers",
    )


def test_summarizer_endpoints():
    print("\n========== Testing Summarizer Endpoints ==========")
    make_request("GET", "/summarizer/status", headers=DEFAULT_HEADERS, description="Summarizer Status")
    make_request("GET", "/summarizer/config", headers=DEFAULT_HEADERS, description="Summarizer Get Config")

    config_data = {"model_name": "gemini-pro-test", "temperature": 0.8}
    make_request(
        "POST", "/summarizer/config", headers=DEFAULT_HEADERS, data=config_data, description="Summarizer Update Config"
    )

    gemini_test_data = {"text": "This is a test sentence for Gemini."}
    make_request(
        "POST",
        "/summarizer/gemini/test",
        headers=DEFAULT_HEADERS,
        data=gemini_test_data,
        description="Summarizer Test Gemini Connection",
    )


def test_users_endpoints():
    print("\n========== Testing Users Endpoints ==========")
    make_request(
        "GET", "/users/", headers=NO_AUTH_HEADERS, description="Users Index"
    )  # Auth not specified, assuming public or adjust

    make_request(
        "GET",
        "/users/viewUser",
        headers=DEFAULT_HEADERS,
        params={"user_identifier": "nonexistent_user@example.com"},
        description="Users View User - Non-existent (expect error)",
    )

    # Create user (Note: backend expects query params for POST /createUser based on api.py)
    new_user_email_users = f"newuser_{int(time.time())}@example.com"
    create_user_params = {
        "email": new_user_email_users,
        "name": "New API User",
        "asu_id": "0987654321",
        "academic_standing": "Freshman",
        "major": "AI",
    }
    make_request(
        "POST",
        "/users/createUser",
        headers=DEFAULT_HEADERS,
        params=create_user_params,
        description="Users Create User (via query params)",
    )

    # GET /user
    make_request(
        "GET",
        "/users/user",
        headers=DEFAULT_HEADERS,
        params={"email": new_user_email_users},
        description="Users Get User by Email (created via /createUser)",
    )

    # POST /user (Update existing or create if not found)
    update_user_data = {"email": new_user_email_users, "name": "Updated API User", "major": "Robotics"}
    make_request(
        "POST",
        "/users/user",
        headers=DEFAULT_HEADERS,
        data=update_user_data,
        description="Users Update User (POST to /user)",
    )

    new_user_for_post_upsert = f"upsert_{int(time.time())}@example.com"
    create_via_post_data = {
        "email": new_user_for_post_upsert,
        "name": "Upsert User",
        "asu_id": "112233",
        "academic_standing": "PHD",
        "major": "Space",
    }
    make_request(
        "POST",
        "/users/user",
        headers=DEFAULT_HEADERS,
        data=create_via_post_data,
        description="Users Create User via POST to /user (Upsert)",
    )

    # /submit-form
    form_data = {"discordID": "TestDiscord123", "role": "Tester"}
    make_request("POST", "/users/submit-form", headers=NO_AUTH_HEADERS, data=form_data, description="Users Submit Form")
