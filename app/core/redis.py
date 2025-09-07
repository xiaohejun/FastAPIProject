from typing import AsyncIterator

from redis.asyncio import from_url, Redis


async def init_redis_pool(url: str) -> AsyncIterator[Redis]:
    client = from_url(url, encoding="utf-8", decode_responses=True)
    yield client
    await client.aclose()