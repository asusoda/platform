"""The fetch the ported sources call. needs_js pages need Firecrawl (FIRECRAWL_URL) to render."""

from modules.knowledge import fetch as knowledge_fetch
from modules.knowledge.fetch import Fetched


def fetch(url: str, *, needs_js: bool = False) -> Fetched:
    return knowledge_fetch.fetch(url)
