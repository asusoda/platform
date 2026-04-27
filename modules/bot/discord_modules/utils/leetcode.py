import secrets

import aiohttp

from modules.utils.logging_config import get_logger

logger = get_logger("bot.leetcode")

LEETCODE_GRAPHQL = "https://leetcode.com/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com",
}


REQUEST_TIMEOUT = aiohttp.ClientTimeout(total=10)


async def fetch_daily_question() -> dict:
    query = """
    query questionOfToday {
      activeDailyCodingChallengeQuestion {
        date
        link
        question {
          frontendQuestionId: questionFrontendId
          title
          titleSlug
          difficulty
          acRate
          paidOnly: isPaidOnly
          topicTags {
            name
            slug
          }
        }
      }
    }
    """
    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        async with session.post(LEETCODE_GRAPHQL, json={"query": query}, headers=HEADERS) as resp:
            if resp.status != 200:
                raise RuntimeError(f"LeetCode API error: {resp.status}")
            data = await resp.json()
    if "errors" in data:
        raise RuntimeError(f"LeetCode GraphQL errors: {data['errors']}")
    try:
        return data["data"]["activeDailyCodingChallengeQuestion"]["question"]
    except (KeyError, TypeError) as exc:
        raise RuntimeError(f"Unexpected LeetCode API response: {data}") from exc


async def fetch_random_question(difficulty: str | None = None) -> dict:
    query = """
    query problemsetQuestionList($categorySlug: String, $limit: Int, $skip: Int, $filters: QuestionListFilterInput) {
      problemsetQuestionList: questionList(
        categorySlug: $categorySlug
        limit: $limit
        skip: $skip
        filters: $filters
      ) {
        total: totalNum
        questions: data {
          frontendQuestionId: questionFrontendId
          title
          titleSlug
          difficulty
          acRate
          paidOnly: isPaidOnly
          topicTags {
            name
            slug
          }
        }
      }
    }
    """
    filters = {}
    if difficulty:
        filters["difficulty"] = difficulty.upper()

    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        # First request: get total count
        async with session.post(
            LEETCODE_GRAPHQL,
            json={
                "query": query,
                "variables": {
                    "categorySlug": "all-code-essentials",
                    "limit": 1,
                    "skip": 0,
                    "filters": filters,
                },
            },
            headers=HEADERS,
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"LeetCode API error: {resp.status}")
            count_data = await resp.json()

        if "errors" in count_data:
            raise RuntimeError(f"LeetCode GraphQL errors: {count_data['errors']}")
        try:
            total = count_data["data"]["problemsetQuestionList"]["total"]
        except (KeyError, TypeError) as exc:
            raise RuntimeError(f"Unexpected LeetCode API response: {count_data}") from exc
        if total <= 0:
            raise RuntimeError("No LeetCode questions found for the selected filters.")
        random_skip = secrets.randbelow(total)

        # Second request: fetch the random problem
        async with session.post(
            LEETCODE_GRAPHQL,
            json={
                "query": query,
                "variables": {
                    "categorySlug": "all-code-essentials",
                    "limit": 1,
                    "skip": random_skip,
                    "filters": filters,
                },
            },
            headers=HEADERS,
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"LeetCode API error: {resp.status}")
            data = await resp.json()

    if "errors" in data:
        raise RuntimeError(f"LeetCode GraphQL errors: {data['errors']}")
    try:
        return data["data"]["problemsetQuestionList"]["questions"][0]
    except (KeyError, TypeError, IndexError) as exc:
        raise RuntimeError(f"Unexpected LeetCode API response: {data}") from exc


async def fetch_recent_ac_submissions(username: str, limit: int = 20) -> list[dict]:
    """Fetch a user's recent accepted submissions. Returns list of {titleSlug, timestamp, ...}.

    Raises RuntimeError if the username is invalid (GraphQL errors or null response).
    """
    query = """
    query recentAcSubmissions($username: String!, $limit: Int!) {
      recentAcSubmissionList(username: $username, limit: $limit) {
        id
        title
        titleSlug
        timestamp
      }
    }
    """
    async with aiohttp.ClientSession(timeout=REQUEST_TIMEOUT) as session:
        async with session.post(
            LEETCODE_GRAPHQL,
            json={"query": query, "variables": {"username": username, "limit": limit}},
            headers=HEADERS,
        ) as resp:
            if resp.status != 200:
                raise RuntimeError(f"LeetCode API error: {resp.status}")
            data = await resp.json()

    if "errors" in data:
        raise RuntimeError(f"LeetCode GraphQL errors: {data['errors']}")
    result = data.get("data", {}).get("recentAcSubmissionList")
    if result is None:
        raise RuntimeError(f"LeetCode username '{username}' not found.")
    return result
