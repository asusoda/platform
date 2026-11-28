"""error_handler and internal_error: a 500 gives an error id and no exception text."""

import logging

from flask import Flask

from core.errors import ServiceError
from core.http.responses import error_handler


def _app() -> Flask:
    app = Flask(__name__)

    @app.route("/boom")
    @error_handler
    def boom():
        raise RuntimeError("secret text /etc/platform")

    @app.route("/refused")
    @error_handler
    def refused():
        raise ServiceError("Not allowed here", 409)

    return app


def test_unhandled_error_hides_the_text_and_logs_it(caplog):
    with caplog.at_level(logging.ERROR):
        response = _app().test_client().get("/boom")
    assert response.status_code == 500
    body = response.get_json()
    assert "secret text" not in response.get_data(as_text=True)
    assert len(body["error_id"]) == 12
    assert body["error_id"] in body["error"]
    logged = [r for r in caplog.records if body["error_id"] in r.getMessage()]
    assert logged and logged[0].exc_info is not None


def test_service_error_keeps_its_message_and_status():
    response = _app().test_client().get("/refused")
    assert response.status_code == 409
    assert response.get_json() == {"error": "Not allowed here"}
