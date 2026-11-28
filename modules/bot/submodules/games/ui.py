from typing import Protocol

import discord

from modules.bot.submodules.games.jeopardy.question import JeopardyQuestion


class GameSessionProtocol(Protocol):
    """What the question post needs from GameSession: the question posts, the team role of a member, and save."""

    question_post: dict

    def get_member_role(self, member: discord.User | discord.Member | None) -> discord.Role | None:
        """The team role of the member, or None."""
        ...

    def save(self) -> None:
        """Write the game state."""
        ...


class QuestionPost(discord.ui.View):
    def __init__(
        self,
        question: JeopardyQuestion,
        voice: discord.StageChannel,
        session: GameSessionProtocol,
        question_uuid: str | None,
        avoid,
    ):
        """
        Initializes the QuestionPost instance.

        Args:
            question (JeopardyQuestion): The question to display.
            voice (discord.StageChannel): The voice channel to move the user to.
            session (GameSessionProtocol): The game of the org.
            question_uuid (Optional[str]): The UUID of the question.
            avoid (Optional[str]): The roles to avoid.
        """
        super().__init__(timeout=None)
        self.question = question
        self.voice = voice
        self.session = session
        self.avoid = avoid
        self.question_uuid = question_uuid

    @discord.ui.button(label="Buzz In", style=discord.ButtonStyle.blurple)
    async def button_callback(self, button: discord.ui.Button, interaction: discord.Interaction):
        user = interaction.user
        # Only a server member can join the stage
        if not isinstance(user, discord.Member):
            await interaction.response.send_message("Only server members can buzz in!", ephemeral=True)
            return
        member_role = self.session.get_member_role(user)
        if member_role in self.avoid:
            await interaction.response.send_message("You are not allowed to buzz in!", ephemeral=True)
        else:
            self.session.question_post[self.question_uuid]["roles_answered"].append(member_role)
            self.session.save()
            button.disabled = True
            button.label = f"{user.name} buzzed in!"
            await interaction.response.edit_message(view=self)
            await user.move_to(self.voice)
            await user.request_to_speak()
