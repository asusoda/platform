"""ASU page extractors and live query sources, ported from SparkyAI's scraper tests. No network."""

import datetime
import xml.etree.ElementTree as ET  # nosec B405 - parses literal test feeds
from pathlib import Path

import pytest

from modules.asu.params import term_code
from modules.asu.registry import QUERY_SOURCES, check, url_for
from modules.asu.sources import SOURCES
from modules.asu.sources.courses import extract_courses
from modules.asu.sources.dining_hours import extract_dining_hours
from modules.asu.sources.events import extract_events
from modules.asu.sources.jobs import extract_jobs
from modules.asu.sources.library_hours import extract_hours
from modules.asu.sources.news import extract_news
from modules.asu.sources.pages import PAGES
from modules.asu.sources.scholarships import extract_scholarships
from modules.asu.sources.shuttles import extract_shuttles
from modules.asu.sources.sports import extract_sports
from modules.asu.text import extract_text, form_page_text
from modules.asu.types import Fetched, QueryError, QuerySource
from modules.knowledge.extract import chunk_text

FIXTURES = Path(__file__).parent / "asu_fixtures"


def page(name: str) -> Fetched:
    markdown = (FIXTURES / name).read_text(encoding="utf-8")
    return Fetched(
        url=f"https://example.invalid/{name}", body=markdown.encode(), content_type="text/markdown", text=markdown
    )


def line_with(text: str, needle: str) -> str:
    matches = [line for line in text.splitlines() if needle in line]
    assert matches, f"no line carries {needle!r}"
    return matches[0]


def test_library_hours_keeps_a_whole_week_on_one_line():
    text = extract_hours(page("library_hours.md"))
    hayden = line_with(text, "Hayden Library")
    assert "Monday 7 a.m. - 2 a.m." in hayden
    assert "Sunday 10 a.m. - 2 a.m." in hayden
    assert "Saturday Closed" in line_with(text, "Noble Library")
    assert "September 8 - September 14, 2025" in text
    assert "|" not in text and "https://" not in text


def test_events_keep_name_date_and_location_together():
    text = extract_events(page("events.md"))
    welcome = line_with(text, "Sun Devil Welcome")
    assert "Thursday, August 21, 2025 5:00 p.m. - 7:00 p.m." in welcome
    assert "Old Main Lawn, Tempe campus" in welcome
    assert "Online via Zoom" in line_with(text, "Graduate Research Showcase")


def test_courses_keep_number_title_and_units_together():
    text = extract_courses(page("courses.md"))
    assert "CSE 110 | Principles of Programming | 3 units" in text
    assert "ACC 494 | Special Topics in Accounting | 1 unit" in text
    assert "https://" not in text


def test_dining_hours_pair_each_day_with_its_hours():
    text = extract_dining_hours(page("dining_hours.md"))
    assert "Monday - Thursday 7:00 a.m. - 9:00 p.m." in line_with(text, "Verde Dining Pavilion")
    assert "Saturday Closed" in line_with(text, "Starbucks")
    assert "&amp;" not in text


def test_scholarships_keep_award_deadline_and_eligibility_together():
    text = extract_scholarships(page("scholarships.md"))
    nau = line_with(text, "New American University Scholarship")
    assert "Award $8,500 per year" in nau and "Deadline February 1, 2026" in nau
    assert "**" not in text


def test_news_keeps_headline_date_and_summary_together():
    text = extract_news(page("news.md"))
    assert "September 3, 2025" in line_with(text, "biodesign building")
    assert "](" not in text


def test_shuttles_keep_route_stops_and_running_times_together():
    text = extract_shuttles(page("shuttles.md"))
    downtown = line_with(text, "Tempe - Downtown Phoenix")
    assert "Stops Tempe Transit Center, Taylor Place, University Center" in downtown
    assert "| ---" not in text


def test_jobs_keep_title_department_pay_and_closing_date_together():
    text = extract_jobs(page("jobs.md"))
    assistant = line_with(text, "Student Office Assistant")
    assert "Pay $15.50 per hour" in assistant and "Closes September 19, 2025" in assistant
    assert "Closes Open until filled" in line_with(text, "Rec Center Lifeguard")


def test_sports_keep_fixture_opponent_date_and_venue_together():
    text = extract_sports(page("sports.md"))
    texas_tech = line_with(text, "Texas Tech")
    assert texas_tech.startswith("Football") and "Date September 13, 2025" in texas_tech


@pytest.mark.parametrize("key", sorted(set(SOURCES) - {p.key for p in PAGES}))
def test_registered_source_carries_its_extractor(key):
    assert callable(SOURCES[key].extractor)


@pytest.mark.parametrize(
    "extractor",
    [
        extract_hours,
        extract_events,
        extract_courses,
        extract_scholarships,
        extract_news,
        extract_shuttles,
        extract_jobs,
        extract_sports,
    ],
)
def test_extractors_fall_back_to_the_raw_body(extractor):
    html = b"<html><body><main><p>CSE 110: Principles of Programming (3)</p></main></body></html>"
    fetched = Fetched(url="https://example.invalid/page", body=html, content_type="text/html")
    assert "Principles of Programming" in extractor(fetched)


def test_an_empty_extraction_yields_no_chunks():
    empty = Fetched(url="https://example.invalid/empty", body=b"", content_type="text/markdown", text="   \n\n")
    assert chunk_text(extract_hours(empty)) == []


def test_term_codes():
    assert term_code("Fall 2024") == "2247"
    assert term_code("Spring 2025") == "2251"
    assert term_code("fall 2026") == "2267"
    for bad in ("Fall", "Autumn 2026", ""):
        with pytest.raises(QueryError, match="term"):
            term_code(bad)


def test_live_sources_registered():
    assert set(QUERY_SOURCES) == {
        "courses",
        "course_catalog",
        "scholarships",
        "events",
        "news",
        "library_catalog",
        "library_hours",
        "study_rooms",
        "sports",
        "sports_news",
        "shuttles",
        "campus_map",
        "social_media",
        "dining",
        "jobs",
        "web",
    }


def test_urls_carry_the_given_filters():
    url = url_for(QUERY_SOURCES["courses"], {"term": "Fall 2026", "keywords": "CSE 310", "level": "undergraduate"})
    assert url.startswith("https://catalog.apps.asu.edu/catalog/classes/classlist?")
    assert "term=2267" in url and "keywords=CSE+310" in url and "level=undergrad" in url
    assert "daysOfWeek" not in url
    catalog = url_for(QUERY_SOURCES["course_catalog"], {"keywords": "CSE 485"})
    assert catalog.startswith("https://catalog.apps.asu.edu/catalog/courses/courselist?") and "term" not in catalog
    assert url_for(QUERY_SOURCES["sports"], {"sport": "Men's Basketball"}) == (
        "https://thesundevils.com/sports/mens-basketball/schedule"
    )
    assert url_for(QUERY_SOURCES["news"], {}) == "https://news.asu.edu/"
    scholarships = url_for(QUERY_SOURCES["scholarships"], {"citizenship": "US Citizen", "focus": "STEM"})
    assert "field_citizenship_status=75" in scholarships and "field_focus=55" in scholarships
    rooms = url_for(QUERY_SOURCES["study_rooms"], {"library": "Hayden", "date": "2026-09-14"})
    assert "lid=13858" in rooms and "date=2026-09-14" in rooms


def test_parameters_are_checked_before_fetching():
    with pytest.raises(QueryError, match="needs: term"):
        url_for(QUERY_SOURCES["courses"], {"keywords": "CSE 310"})
    with pytest.raises(QueryError, match="no parameter"):
        url_for(QUERY_SOURCES["courses"], {"term": "Fall 2026", "subject": "CSE"})
    with pytest.raises(QueryError, match="takes: nothing"):
        url_for(QUERY_SOURCES["library_hours"], {"library": "hayden"})
    with pytest.raises(QueryError, match="undergraduate"):
        url_for(QUERY_SOURCES["courses"], {"term": "Fall 2026", "level": "phd"})
    with pytest.raises(QueryError, match="date must look like"):
        url_for(QUERY_SOURCES["study_rooms"], {"library": "hayden", "date": "Sep 14"})
    with pytest.raises(QueryError, match="campus"):
        url_for(QUERY_SOURCES["dining"], {"campus": "polytechnic"})
    check(QUERY_SOURCES["courses"], {"term": "Fall 2026", "days": "Monday, WEDNESDAY"})
    with pytest.raises(QueryError, match="takes one value"):
        check(QUERY_SOURCES["shuttles"], {"route": "mercado, polytechnic-tempe"})


def test_a_live_source_reuses_the_scheduled_extractor():
    assert QUERY_SOURCES["library_hours"].extractor is SOURCES["library_hours"].extractor


def test_a_source_sets_exactly_one_way_to_be_fetched():
    with pytest.raises(ValueError, match="exactly one"):
        QuerySource(key="x", description="x", params=())


def test_a_form_page_keeps_its_results():
    html = b"<main><form><ul><li>Robotics Club</li></ul></form></main>"
    fetched = Fetched(url="https://x.test", body=html, content_type="text/html")
    assert "Robotics Club" in form_page_text(fetched)
    assert "Robotics Club" not in extract_text(html)


def test_shuttle_times_in_arizona_time():
    from modules.asu.http import ARIZONA
    from modules.asu.queries.shuttles import render

    now = datetime.datetime(2026, 9, 12, 16, 0, tzinfo=ARIZONA)

    def at(h, m):
        return int(datetime.datetime(2026, 9, 12, h, m, tzinfo=ARIZONA).timestamp())

    routes = [{"routeID": 1, "longName": "Mercado"}, {"routeID": 2, "longName": "Polytechnic-Tempe"}]
    stops = [{"stopID": 10, "longName": "Lot 37"}, {"stopID": 11, "longName": "SIM Building"}]
    etas = [
        {"stopID": 10, "routeID": 2, "ETA1": at(16, 54), "ETA2": at(18, 54)},
        {"stopID": 11, "routeID": 2, "ETA1": at(16, 44), "ETA2": 0},
    ]
    out = render(routes, stops, etas, None, now)
    assert "as of 4:00 PM" in out
    assert out.index("SIM Building: next 4:44 PM") < out.index("Lot 37: next 4:54 PM, then 6:54 PM")


def test_campus_places_are_plain_and_linked():
    from modules.asu.queries.campus_map import render

    hayden = {
        "attributes": {"Name": "Hayden Library", "Type": "Library", "Description": "<p>Books &amp; more</p>"},
        "geometry": {"x": -111.935242, "y": 33.418938},
    }
    out = render("hayden", [hayden, hayden])
    assert out.count("Hayden Library") == 1 and "Books & more" in out
    assert "query=33.418938,-111.935242" in out


def test_feeds_are_narrowed():
    from modules.asu.queries.social_media import posts_of
    from modules.asu.queries.sports_news import official_lines

    rss = ET.fromstring(  # nosec B314 - literal test input
        "<rss><channel>"
        "<item><title>Football wins</title><link>https://t/1</link>"
        "<pubDate>Sat, 12 Sep 2026 03:55:21 GMT</pubDate><sports>Football</sports></item>"
        "<item><title>Volleyball wins</title><link>https://t/2</link><sports>Volleyball</sports></item>"
        "</channel></rss>"
    )
    assert official_lines(rss, "football", "") == ["Fri Sep 11, 2026 | Football wins | https://t/1"]
    atom = ET.fromstring(  # nosec B314 - literal test input
        '<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>Football intro</title>'
        '<link href="https://y/1"/><published>2026-09-12T15:45:23+00:00</published></entry>'
        '<entry><title>Scholarships</title><link href="https://y/2"/></entry></feed>'
    )
    assert len(posts_of(atom, "football")) == 1 and len(posts_of(atom, "")) == 2


def test_web_results():
    from modules.asu.queries.web import render

    found = {
        "answers": [{"answer": "ASU beat Morgan State 70-7."}],
        "results": [
            {"url": "https://a.test/s", "title": "Schedule", "content": "<b>Sun Devil</b> &amp; more"},
            {"url": "https://a.test/s", "title": "duplicate"},
        ],
    }
    out = render("asu football", found, limit=8, snippet_chars=300)
    assert "Answer: ASU beat Morgan State 70-7." in out and "Sun Devil & more" in out
    assert "duplicate" not in out
    with pytest.raises(QueryError, match="duckduckgo"):
        render("x", {"results": [], "unresponsive_engines": [["duckduckgo", "CAPTCHA"]]}, 8, 300)
