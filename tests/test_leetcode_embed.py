"""Checks for the LeetCode question embed builder."""

from modules.bot.discord_modules.cogs.LeetCodeCog import build_question_embed

QUESTION = {
    "title": "Two Sum",
    "titleSlug": "two-sum",
    "difficulty": "Easy",
    "acRate": 55.5,
    "frontendQuestionId": "1",
    "topicTags": [{"name": "Array", "slug": "array"}, {"name": "Hash Table", "slug": "hash-table"}],
}


def _field(embed, name):
    return next(f.value for f in embed.fields if f.name == name)


def test_topics_are_hidden_behind_a_spoiler():
    topics = _field(build_question_embed(QUESTION, is_daily=True), "Topics")
    assert topics.startswith("||") and topics.endswith("||"), topics
    # The tag names must not leak outside the spoiler markers.
    assert "Array" in topics and "Hash Table" in topics
    assert topics.index("Array") > 1


def test_question_without_topics_is_not_an_empty_spoiler():
    question = {**QUESTION, "topicTags": []}
    assert _field(build_question_embed(question), "Topics") == "None"


def test_difficulty_stays_visible():
    embed = build_question_embed(QUESTION)
    assert _field(embed, "Difficulty") == "Easy"
