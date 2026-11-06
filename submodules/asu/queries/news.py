"""ASU News stories: the newest on the front page, or a search by keyword."""

from __future__ import annotations

from modules.submodules.params import text, url
from modules.submodules.types import QueryParam, QuerySource
from submodules.asu.params import topic

# Words that ask for recent stories rather than name a topic.
_NOT_A_TOPIC = {"latest", "recent", "new", "newest", "today", "news", "asu", "stories", "top"}


def to_url(params: dict[str, str]) -> str:
    """The news search results for a topic, or the front page without one."""
    keywords = text(params, "keywords")
    if not set(keywords.lower().split()) - _NOT_A_TOPIC:
        return "https://news.asu.edu/"
    return url("https://news.asu.edu/search", [("search", keywords)])


def news_topic(query: str) -> str:
    """The topic words of query, without words that only ask for recent stories."""
    return " ".join(w for w in topic(query).split() if w.lower() not in _NOT_A_TOPIC)


QUERY = QuerySource(
    key="news",
    description="The newest ASU News stories, or a search of ASU News by topic. Example: keywords robotics.",
    params=(QueryParam("keywords", "Topic to search for. Leave out for the newest stories.", example="robotics"),),
    to_url=to_url,
    category="news",
    query_param="keywords",
    narrow=news_topic,
)
