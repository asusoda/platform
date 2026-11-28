"""Games: the Jeopardy JSON format check, the stored games of each org, the org of a game request, the active game
rows and reading a game from the data folder. No Flask here."""

import json
import os
import re

from sqlalchemy.orm import Session

from core.errors import ServiceError
from modules.bot.submodules.games import models
from modules.organizations import service as organizations
from modules.organizations.models import Organization

SAFE_FILENAME = re.compile(r"^[\w\-]+$")
GAME_KEYS = {"name", "description", "players", "categories", "per_category", "teams", "uuid"}
QUESTION_KEYS = {"question", "answer", "value", "uuid"}


class GameError(ServiceError):
    pass


def enabled_for_guilds(session, guild_ids) -> bool:
    """Whether an org on one of these Discord servers has the games module on."""
    orgs = session.query(Organization).filter(Organization.guild_id.in_([str(g) for g in guild_ids])).all()
    return any(organizations.module_enabled(org, "bot.games") for org in orgs)


def is_valid_game(data: dict) -> bool:
    """Whether data has a game object with every game key and questions with every question key."""
    if "game" not in data or "questions" not in data:
        return False
    if not all(key in data["game"] for key in GAME_KEYS):
        return False
    for _category, questions in data["questions"].items():
        for question in questions:
            if not all(key in question for key in QUESTION_KEYS):
                return False
    return True


def list_games(session: Session, org_id: int) -> list[dict]:
    """The game JSON of each stored game of the org, in the order the games were added."""
    rows = (
        session.query(models.JeopardyGame)
        .filter(models.JeopardyGame.organization_id == org_id)
        .order_by(models.JeopardyGame.id)
        .all()
    )
    return [row.data for row in rows if isinstance(row.data, dict)]


def _game_row(session: Session, org_id: int, name: str) -> models.JeopardyGame | None:
    return (
        session.query(models.JeopardyGame)
        .filter(models.JeopardyGame.organization_id == org_id, models.JeopardyGame.name == name)
        .first()
    )


def get_game(session: Session, org_id: int, name: str) -> dict:
    """The game JSON of the org's stored game with this name. Raises GameError (404) when there is no such game."""
    row = _game_row(session, org_id, name)
    if row is None or not isinstance(row.data, dict):
        raise GameError("Game not found", 404)
    return row.data


def save_game(session: Session, org_id: int, data: dict) -> models.JeopardyGame:
    """Store a game JSON for the org. The org's stored game with the same data["game"]["name"] gets the new data."""
    if not is_valid_game(data):
        raise GameError("Invalid game JSON format")
    name = data["game"]["name"]
    row = _game_row(session, org_id, name)
    if row is None:
        row = models.JeopardyGame(organization_id=org_id, name=name, data=data)
        session.add(row)
    else:
        row.data = data
    session.commit()
    return row


def game_org(
    session: Session, allowed: frozenset[str] | None, prefix: str | None, guild_id: str | None
) -> Organization:
    """The org that a game request works on.

    allowed is the guild ids of the caller's orgs, or None for a caller with no limit (the superadmin). The org is an
    active org with bot.games on, in allowed, that has this prefix and guild id when they are set. A caller with no
    limit must set prefix or guild_id. Raises GameError (400) when no org or more than one org matches.
    """
    if allowed is None and not prefix and not guild_id:
        raise GameError("Set org to the prefix of the org of the game")
    query = session.query(Organization).filter(Organization.is_active.is_(True))
    if prefix:
        query = query.filter(Organization.prefix == prefix)
    if guild_id:
        query = query.filter(Organization.guild_id == str(guild_id))
    orgs = [
        org
        for org in query.order_by(Organization.id).all()
        if (allowed is None or str(org.guild_id) in allowed) and organizations.module_enabled(org, "bot.games")
    ]
    if len(orgs) == 1:
        return orgs[0]
    if not orgs:
        raise GameError("No org where you are an officer has games on")
    raise GameError("You are an officer in more than one org with games on. Set org to the prefix of the org")


def save_state(session: Session, org_id: int, guild_id: int, game_data: dict, helper_data: dict) -> None:
    """Write the active game row of the org. Commits."""
    row = session.query(models.ActiveGame).filter(models.ActiveGame.organization_id == org_id).first()
    if row is None:
        row = models.ActiveGame(organization_id=org_id)
        session.add(row)
    row.guild_id = str(guild_id)
    row.name = str(game_data["game"]["name"])
    row.game_data = game_data
    row.helper_data = helper_data
    session.commit()


def clear_state(session: Session, org_id: int) -> None:
    """Delete the active game row of the org. Commits."""
    session.query(models.ActiveGame).filter(models.ActiveGame.organization_id == org_id).delete()
    session.commit()


def states(session: Session) -> list[models.ActiveGame]:
    """Every active game row, oldest org first."""
    return session.query(models.ActiveGame).order_by(models.ActiveGame.organization_id).all()


def read_game_file(file_name: object) -> dict:
    """The JSON of ./data/<file_name>.json. The name holds only letters, digits, - and _."""
    if not file_name or not isinstance(file_name, str):
        raise GameError("Missing or invalid file_name parameter")
    if not SAFE_FILENAME.match(file_name):
        raise GameError("Invalid file name")
    base_dir = os.path.abspath("./data")
    requested_path = os.path.abspath(os.path.join(base_dir, f"{file_name}.json"))
    if not requested_path.startswith(base_dir + os.sep):
        raise GameError("Attempted path traversal or invalid path")
    if not os.path.isfile(requested_path):
        raise GameError("Game file not found", 404)
    with open(requested_path) as f:
        return json.load(f)
