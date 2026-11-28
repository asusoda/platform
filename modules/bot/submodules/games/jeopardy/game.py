import uuid

import discord

from core.log import get_logger
from modules.bot.submodules.games.jeopardy.question import JeopardyQuestion
from modules.bot.submodules.games.jeopardy.team import Team

logger = get_logger("modules.bot.submodules.games.jeopardy.Jeopardy")


class JeopardyGame:
    """
    Manages a Jeopardy-style game in a Discord environment. It handles game initialization,
    team and player management, question handling, and game state tracking.

    Attributes:
        name (str): The name of the Jeopardy game.
        description (str): A description of the game.
        teams (list): A list of Team objects participating in the game.
        players (list): A list of Discord Members participating in the game.
        categories (list): Categories of questions in the game.
        per_category (int): Number of questions per category.
        questions (dict): A dictionary mapping categories to their respective questions.
        uuid (uuid.UUID): A unique identifier for the game.
        is_announced (bool): Flag indicating if the game has been announced.
        is_started (bool): Flag indicating if the game has started.
    """

    def __init__(self, game_data):
        """
        Initializes the JeopardyGame instance with provided game data.

        Args:
            game_data (dict): Data required to set up the game.
        """
        self.name = game_data["game"]["name"]
        self.description = game_data["game"]["description"]
        self.teams = self._create_teams(game_data["game"]["teams"])
        self.players: list[discord.Member | discord.User] = []
        self.categories = game_data["game"]["categories"]
        self.per_category = game_data["game"]["per_category"]
        self.questions = self._create_questions(game_data["questions"])
        self.uuid = uuid.uuid4()
        self.is_announced = False
        self.is_started = False

    @classmethod
    def from_json(cls, state: dict) -> "JeopardyGame":
        """The game that to_json() gave this state: the same uuid, flags, scores, question ids and answered flags.

        Players and team members are not in the state. The caller adds them.
        """
        info = state["game"]
        game = cls(
            {
                "game": {
                    "name": info["name"],
                    "description": info["description"],
                    "teams": [team["name"] for team in info["teams"]],
                    "categories": info["categories"],
                    "per_category": info["per_category"],
                },
                "questions": state["questions"],
            }
        )
        game.uuid = uuid.UUID(info["uuid"])
        game.is_announced = bool(info.get("announced"))
        game.is_started = bool(info.get("started"))
        for team, saved in zip(game.teams, info["teams"], strict=True):
            team.score = int(saved.get("score", 0))
        for category, questions in game.questions.items():
            for question, saved in zip(questions, state["questions"][category], strict=True):
                question.id = saved["id"]
                question.answered = bool(saved.get("answered"))
        return game

    def to_json(self):
        """
        Converts the JeopardyGame instance to a JSON-serializable dictionary.

        Returns:
            dict: A dictionary representation of the game.
        """
        quest = {}
        for question in self._all_questions():
            if question.category not in quest:
                quest[question.category] = []
            quest[question.category].append(question.to_json())

        return {
            "game": {
                "name": self.name,
                "description": self.description,
                "teams": [team.to_json() for team in self.teams],
                "categories": self.categories,
                "per_category": self.per_category,
                "uuid": str(self.uuid),
                "announced": self.is_announced,
                "started": self.is_started,
            },
            "questions": quest,
        }

    def _all_questions(self) -> list[JeopardyQuestion]:
        """Every question of the game, category by category."""
        return [question for questions in self.questions.values() for question in questions]

    def _create_questions(self, questions_data) -> dict[str, list[JeopardyQuestion]]:
        """
        Creates and organizes JeopardyQuestion objects from provided data.

        Args:
            questions_data (dict): Question data categorized by their categories.

        Returns:
            dict: Organized questions by category.
        """
        logger.debug(f"Questions data structure: {questions_data}")
        questions_dict: dict[str, list[JeopardyQuestion]] = {}
        for category in questions_data.keys():
            questions_dict[category] = []
            for question in questions_data[category]:
                questions_dict[category].append(
                    JeopardyQuestion(
                        category,
                        question["question"],
                        question["answer"],
                        question["value"],
                    )
                )
        return questions_dict

    def _create_teams(self, data) -> list[Team]:
        """
        Creates Team objects from provided data.

        Args:
            data (list): Data for creating teams.

        Returns:
            list: A list of initialized Team objects.
        """
        return [Team(team_data) for team_data in data]

    def award_points(self, team_name, points):
        """
        Awards points to a specified team.

        Args:
            team_name (str): The name of the team.
            points (int): The number of points to award.

        Returns:
            bool: True if points were successfully awarded, False otherwise.
        """
        team = next((team for team in self.teams if team.name == team_name), None)
        if team:
            team.add_points(points)
            return True
        return False

    def start(self):
        """
        Marks the game as started.
        """
        self.is_started = True

    def add_member(self, member: discord.Member | discord.User):
        """
        Adds a player
        """
        self.players.append(member)

    def remove_member(self, member: discord.Member | discord.User) -> bool:
        """Removes a player. False when the member is not a player."""
        for player in self.players:
            if player.id == member.id:
                self.players.remove(player)
                return True
        return False

    def get_question_by_uuid(self, uuid: str) -> JeopardyQuestion | None:
        """
        Retrieves a question by its UUID.

        Args:
            uuid (uuid.UUID): The UUID of the question.

        Returns:
            JeopardyQuestion or None: The question object if found, otherwise None.
        """
        for question in self._all_questions():
            if question.id == uuid:
                return question
        return None

    def answer_question(self, uuid: str) -> tuple[bool, JeopardyQuestion | None]:
        """
        Marks a question as answered in a specific category and value.

        Args:
            uuid (uuid.UUID): The UUID of the question.

        Returns:
            tuple[bool, JeopardyQuestion | None]: A tuple of (success, question) where success is True if the question was successfully marked as answered, False otherwise, and question is the answered question or None.
        """
        question = self.get_question_by_uuid(uuid)
        if question:
            question.answered = True
            return True, question
        return False, None

    def get_winners(self) -> list[str]:
        """
        Retrieves the members of the winning team(s).

        Returns:
            list: The display names of the members of the teams with the highest score.
        """
        winners: list[str] = []
        if not self.teams:
            return winners
        max_points = max(team.score for team in self.teams)
        for team in self.teams:
            if team.score == max_points:
                for member in team.members:
                    winners.append(member.display_name)
        return winners

    def attach_roles(self, roles: list[discord.Role]) -> None:
        """
        Attaches roles to teams
        """
        for team in self.teams:
            for role in roles:
                if team.name == role.name:
                    team.attach_role(role)

    def get_members(self) -> list[discord.Member | discord.User]:
        """
        Retrieves the members of the game
        """
        return self.players

    def get_board(self):
        """
        Retrieves the board
        """
        data: dict[str, list[int | str]] = {}
        for question in self._all_questions():
            if question.category not in data.keys():
                data[question.category] = []
            if not question.answered:
                data[question.category].append(question.value)
            else:
                data[question.category].append("XXXX")

        return data
