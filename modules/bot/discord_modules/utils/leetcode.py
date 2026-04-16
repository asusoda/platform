import random

import aiohttp

from modules.utils.logging_config import get_logger

logger = get_logger("bot.leetcode")

LEETCODE_GRAPHQL = "https://leetcode.com/graphql"
HEADERS = {
    "Content-Type": "application/json",
    "Referer": "https://leetcode.com",
}


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
    async with aiohttp.ClientSession() as session:
        async with session.post(LEETCODE_GRAPHQL, json={"query": query}, headers=HEADERS) as resp:
            if resp.status != 200:
                raise RuntimeError(f"LeetCode API error: {resp.status}")
            data = await resp.json()
    return data["data"]["activeDailyCodingChallengeQuestion"]["question"]


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

    async with aiohttp.ClientSession() as session:
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

        total = count_data["data"]["problemsetQuestionList"]["total"]
        random_skip = random.randint(0, total - 1)

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

    return data["data"]["problemsetQuestionList"]["questions"][0]
