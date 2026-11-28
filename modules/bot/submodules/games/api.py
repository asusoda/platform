"""Game controls at /api/bot. Each route works on the games of one org: the org of the caller, or the org set with
org (prefix) or guild_id. The superadmin must set one of them."""

import asyncio
import functools
import inspect
import json
from collections.abc import Callable, Coroutine
from typing import Any

import discord
from flask import Blueprint, current_app, jsonify, request

from core.db import db_connect as db
from core.http.responses import internal_error
from core.log import get_logger
from modules.auth.access import any_officer_denial, current_principal, is_superadmin, officer_guild_ids
from modules.bot.bot import BotFork

from . import service
from .cog import GameCog
from .session import GameSession

logger = get_logger(__name__)

game_blueprint = Blueprint("game", __name__, template_folder=None, static_folder=None)


@game_blueprint.before_request
def require_officer():
    """The game controls post to Discord and award points, so only officers may call them."""
    denial = any_officer_denial()
    if denial:
        return jsonify({"message": denial[0]}), denial[1]
    if not _games_on():
        return jsonify({"message": "The games feature is off for your organization"}), 404
    return None


def _games_on() -> bool:
    """Whether the caller is an officer of an org with the games module on. The superadmin always is."""
    principal = current_principal()
    if principal is None or not principal.discord_id or is_superadmin(principal.discord_id):
        return True
    guilds = officer_guild_ids(principal.discord_id)
    if not guilds:
        return True
    session = db.SessionLocal()
    try:
        return service.enabled_for_guilds(session, guilds)
    finally:
        session.close()


def _errors(view: Callable) -> Callable:
    """Turn a GameError into {"error": message} with its status, and any other exception into internal_error."""
    if inspect.iscoroutinefunction(view):

        @functools.wraps(view)
        async def run_async(*args, **kwargs):
            try:
                return await view(*args, **kwargs)
            except service.GameError as e:
                return jsonify({"error": e.message}), e.status
            except Exception:
                return internal_error(run_async.__name__)

        return run_async

    @functools.wraps(view)
    def run(*args, **kwargs):
        try:
            return view(*args, **kwargs)
        except service.GameError as e:
            return jsonify({"error": e.message}), e.status
        except Exception:
            return internal_error(run.__name__)

    return run


def _allowed_guilds() -> frozenset[str] | None:
    """The guild ids of the caller's orgs. None for the superadmin and for a caller with no Discord id."""
    principal = current_principal()
    if principal is None or not principal.discord_id or is_superadmin(principal.discord_id):
        return None
    return officer_guild_ids(principal.discord_id) or frozenset()


def _game_org() -> tuple[int, str]:
    """The id and guild id of the org whose games this request works on. Raises GameError."""
    session = db.SessionLocal()
    try:
        org = service.game_org(session, _allowed_guilds(), request.values.get("org"), request.values.get("guild_id"))
        return org.id, str(org.guild_id)
    finally:
        session.close()


def _ready_bot() -> BotFork | None:
    """The bot of this process when it runs here and is ready, else None."""
    bot = getattr(current_app, "auth_bot", None)
    if isinstance(bot, BotFork) and bot.is_ready():
        return bot
    return None


async def _on_bot(bot: BotFork, coro: Coroutine[Any, Any, Any]) -> Any:
    """Run coro on the bot's event loop and wait for its result. Discord objects work only on that loop."""
    try:
        loop = bot.loop
    except AttributeError:
        loop = None
    if loop is None or loop is asyncio.get_running_loop() or not loop.is_running():
        return await coro
    return await asyncio.wrap_future(asyncio.run_coroutine_threadsafe(coro, loop))


def _game_cog(bot: BotFork) -> GameCog | None:
    """The GameCog of the bot, or None when the bot does not have it."""
    cog = bot.get_cog("GameCog")
    return cog if isinstance(cog, GameCog) else None


def _live() -> tuple[BotFork, GameCog, int, discord.Guild]:
    """The bot, its GameCog, and the id and Discord server of the org of the request. Raises GameError."""
    bot = _ready_bot()
    if bot is None:
        logger.warning("game route %s: the bot is not ready or not in this process", request.path)
        raise service.GameError("Auth bot is not available or not ready.", 503)
    cog = _game_cog(bot)
    if cog is None:
        logger.error("game route %s: the bot has no GameCog", request.path)
        raise service.GameError("GameCog not found", 500)
    org_id, guild_id = _game_org()
    guild = bot.get_guild(int(guild_id))
    if guild is None:
        raise service.GameError("The bot is not in the Discord server of this org")
    return bot, cog, org_id, guild


def _live_session() -> tuple[BotFork, GameSession]:
    """The bot and the game session of the org of the request. Raises GameError (400) when no game is set up."""
    bot, cog, _org_id, guild = _live()
    session = cog.session(guild.id)
    if session is None:
        raise service.GameError("No active game is set up")
    return bot, session


@game_blueprint.route("/", methods=["GET"])
def game_index():
    logger.debug("Game API index endpoint called")
    return jsonify({"message": "game api for auth_bot"}), 200


@game_blueprint.route("/getavailablegames", methods=["GET"])
@_errors
def get_available_games():
    org_id, _guild_id = _game_org()
    session = db.SessionLocal()
    try:
        games = [game["game"] for game in service.list_games(session, org_id)]
    finally:
        session.close()
    logger.debug("games listed org_id=%s count=%s", org_id, len(games))
    return jsonify([{"name": g["name"], "description": g["description"], "uuid": g["uuid"]} for g in games]), 200


@game_blueprint.route("/gamedata", methods=["GET"])
@_errors
def get_game_data():
    return jsonify(service.read_game_file(request.args.get("file_name")))


@game_blueprint.route("/startgame", methods=["POST"])
@_errors
def start_game():
    game_name = request.form["name"]
    org_id, _guild_id = _game_org()
    session = db.SessionLocal()
    try:
        service.get_game(session, org_id, game_name)
    finally:
        session.close()
    return jsonify({"message": f"Game {game_name} started", "status": "success"}), 200


@game_blueprint.route("/stopgame", methods=["POST"])
def stop_game():
    return jsonify({"message": "Game stopped", "status": "success"}), 200


@game_blueprint.route("/uploadgame", methods=["POST"])
@_errors
def upload_game():
    if "file" not in request.files:
        return jsonify({"error": "No file part"}), 400
    file = request.files["file"]
    if file.filename == "":
        return jsonify({"error": "No selected file"}), 400
    org_id, _guild_id = _game_org()
    try:
        game_data = json.loads(file.read().decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        logger.warning("game upload is not JSON org_id=%s file=%s", org_id, file.filename)
        return jsonify({"error": "Invalid JSON"}), 400
    if not isinstance(game_data, dict) or not service.is_valid_game(game_data):
        logger.warning("game upload has a bad format org_id=%s file=%s", org_id, file.filename)
        return jsonify({"error": "Invalid game JSON format"}), 400
    session = db.SessionLocal()
    try:
        service.save_game(session, org_id, game_data)
    finally:
        session.close()
    logger.info("game uploaded org_id=%s game=%s", org_id, game_data["game"]["name"])
    return jsonify({"message": "File uploaded and validated successfully"}), 200


@game_blueprint.route("/getgame", methods=["GET"])
@_errors
def get_game():
    name = request.args.get("name")
    if not name:
        return jsonify({"error": "Game not found"}), 404
    org_id, _guild_id = _game_org()
    session = db.SessionLocal()
    try:
        game_doc = service.get_game(session, org_id, name)
    finally:
        session.close()
    return jsonify({"info": game_doc["game"], "questions": game_doc["questions"]}), 200


@game_blueprint.route("/setactivegame", methods=["POST"])
@_errors
async def set_active_game():
    bot, cog, org_id, guild = _live()
    name = request.args.get("name") or ""
    session = db.SessionLocal()
    try:
        game = service.get_game(session, org_id, name)
    finally:
        session.close()
    if cog.is_setup(guild.id):
        return jsonify({"error": "A game is set up in Discord. Clean it with /cleanactivegame first"}), 409
    date, time = request.args.get("date"), request.args.get("time")
    cog.set_game(org_id, guild, {"game": game["game"], "questions": game["questions"]}, date, time)
    await _on_bot(bot, cog.setup_game(guild.id))
    logger.info("active game set org_id=%s guild_id=%s game=%s", org_id, guild.id, name)
    return jsonify({"message": "Active game set successfully"}), 200


@game_blueprint.route("/getactivegame", methods=["GET"])
@_errors
async def get_active_game():
    _bot, cog, _org_id, guild = _live()
    game_data = cog.get_game(guild.id)
    if game_data is None:
        return jsonify({"error": "No active game set"}), 404
    return jsonify(game_data), 200


@game_blueprint.route("/cleanactivegame", methods=["POST"])
@_errors
async def clean_active_game():
    bot, cog, org_id, guild = _live()
    await _on_bot(bot, cog.clear_game(guild.id))
    logger.info("active game cleaned org_id=%s guild_id=%s", org_id, guild.id)
    return jsonify({"message": "Active game cleaned successfully"}), 200


@game_blueprint.route("/getactivegamestate", methods=["GET"])
@_errors
def get_active_game_state():
    # The state is the JSON of the game: teams, scores, questions and the announced and started flags
    _bot, cog, _org_id, guild = _live()
    game_data = cog.get_game(guild.id)
    if game_data is None:
        return jsonify({"error": "No active game set or state unavailable"}), 404
    return jsonify(game_data), 200


@game_blueprint.route("/startactivegame", methods=["POST"])
@_errors
async def start_active_game():
    bot, session = _live_session()
    if not await _on_bot(bot, session.start()):
        return jsonify({"error": "No active game is set up"}), 400
    logger.info("active game started org_id=%s", session.org_id)
    return jsonify({"message": "Active game started successfully"}), 200


@game_blueprint.route("/endactivegame", methods=["POST"])
@_errors
async def end_active_game():
    bot, session = _live_session()
    if not await _on_bot(bot, session.end()):
        return jsonify({"error": "No active game is set up"}), 400
    logger.info("active game ended org_id=%s", session.org_id)
    return jsonify({"message": "Active game ended successfully"}), 200


@game_blueprint.route("/revealquestion", methods=["POST"])
@_errors
async def reveal_question():
    uuid = request.args.get("uuid")
    if not uuid:
        return jsonify({"error": "Missing uuid parameter"}), 400
    bot, session = _live_session()
    if not await _on_bot(bot, session.show_question(uuid)):
        return jsonify({"error": "No active game is set up or the question is not found"}), 400
    logger.info("question revealed org_id=%s question=%s", session.org_id, uuid)
    return jsonify({"message": "Question revealed successfully"}), 200


@game_blueprint.route("/revealanswer", methods=["POST"])
@_errors
async def reveal_answer():
    uuid = request.args.get("uuid")
    if not uuid:
        return jsonify({"error": "Missing uuid parameter"}), 400
    bot, session = _live_session()
    if not await _on_bot(bot, session.show_answer(uuid)):
        return jsonify({"error": "No active game is set up or the question is not found"}), 400
    logger.info("answer revealed org_id=%s question=%s", session.org_id, uuid)
    return jsonify({"message": "Answer revealed successfully"}), 200


@game_blueprint.route("/awardpoints", methods=["POST"])
@_errors
async def award_points():
    team = request.args.get("team")
    points = request.args.get("points")
    if not team or not points:
        return jsonify({"error": "Missing team or points parameter"}), 400
    try:
        amount = int(points)
    except ValueError:
        return jsonify({"error": "points must be a whole number"}), 400
    bot, session = _live_session()
    if not await _on_bot(bot, session.award_points(team, amount)):
        return jsonify({"error": "No active game is set or the team is not found"}), 400
    logger.info("points awarded org_id=%s team=%s points=%s", session.org_id, team, amount)
    return jsonify({"message": "Points awarded successfully"}), 200
