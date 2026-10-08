"""Settings the ported ASU sources read, from the environment."""

import os
from types import SimpleNamespace


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def settings() -> SimpleNamespace:
    return SimpleNamespace(
        scraper=SimpleNamespace(query_max_chars=_int("ASU_QUERY_MAX_CHARS", 30_000)),
        search=SimpleNamespace(
            base_url=os.environ.get("SEARXNG_URL", "").strip(),
            engines=os.environ.get("SEARXNG_ENGINES", "google,brave,bing"),
            language="en-US",
            safesearch=1,
            max_results=8,
            snippet_chars=300,
        ),
    )
