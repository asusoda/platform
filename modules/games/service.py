"""Game files: the Jeopardy JSON format check and reading a game from the data folder. No Flask here."""

import json
import os
import re

from core.errors import ServiceError

SAFE_FILENAME = re.compile(r"^[\w\-]+$")
GAME_KEYS = {"name", "description", "players", "categories", "per_category", "teams", "uuid"}
QUESTION_KEYS = {"question", "answer", "value", "uuid"}


class GameError(ServiceError):
    pass


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
    with open(requested_path) as f:
        return json.load(f)
