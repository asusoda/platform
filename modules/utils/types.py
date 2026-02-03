"""Custom type definitions for the application."""

from flask import Request as FlaskRequest


class ExtendedRequest(FlaskRequest):
    """Extended Request class with custom attributes."""

    clerk_user_email: str | None
