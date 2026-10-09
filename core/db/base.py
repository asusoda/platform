import uuid

from sqlalchemy.orm import declarative_base

Base = declarative_base()


def new_uuid() -> str:
    """A random UUID as text, the default of string primary keys."""
    return str(uuid.uuid4())
