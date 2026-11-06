"""Sun Devil Central clubs and events, read with the org's ASU sign-in."""

from modules.submodules.types import QueryParam, QuerySource
from submodules.asu.signin import sundevil_central

_KEYWORDS = QueryParam("keywords", "Words to match, such as a club's topic or an event's name", required=True)

CLUBS = QuerySource(
    key="clubs",
    description="ASU student clubs on Sun Devil Central: campus, categories, link, contact and mission. Needs the "
    "org's ASU sign-in.",
    params=(_KEYWORDS,),
    to_url=lambda p: sundevil_central.clubs_url(p["keywords"]),
    extractor=sundevil_central.extract_clubs,
    signin="asu",
    index=False,
    category="clubs",
)

CLUB_EVENTS = QuerySource(
    key="club_events",
    description="Events that ASU clubs post on Sun Devil Central: time, place and link. Needs the org's ASU sign-in.",
    params=(_KEYWORDS,),
    to_url=lambda p: sundevil_central.events_url(p["keywords"]),
    extractor=sundevil_central.extract_events,
    signin="asu",
    index=False,
    category="events",
)
