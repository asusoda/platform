"""The ASU Library catalog: books, articles, journals and media."""

from __future__ import annotations

import urllib.parse

from modules.packs.params import choices, code, text
from modules.packs.types import QueryParam, QuerySource

_TYPES = {
    "all": "any",
    "books": "books",
    "articles": "articles",
    "journals": "journals",
    "images": "images",
    "scores": "scores",
    "maps": "maps",
    "sound recordings": "audios",
    "video": "videos",
}


def to_url(params: dict[str, str]) -> str:
    """The catalog search URL. Primo takes its query as a comma-separated expression."""
    query = {
        "query": f"any,contains,{text(params, 'keywords')},AND",
        "pfilter": f"rtype,exact,{code(params, 'type', _TYPES) or 'any'}",
        "tab": "LibraryCatalog",
        "search_scope": "MyInstitution",
        "vid": "01ASU_INST:01ASU",
        "lang": "en",
        "mode": "advanced",
        "offset": "0",
    }
    return "https://search.lib.asu.edu/discovery/search?" + urllib.parse.urlencode(query)


QUERY = QuerySource(
    key="library_catalog",
    description="Search the ASU Library catalog for books, articles, journals and media.",
    params=(
        QueryParam("keywords", "Title, author or subject.", required=True, example="deep learning"),
        QueryParam("type", "Resource type.", choices=choices(_TYPES)),
    ),
    to_url=to_url,
    needs_js=True,
    category="library",
)
