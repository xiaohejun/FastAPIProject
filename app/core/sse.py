import asyncio
from redis.asyncio import Redis
from sse_starlette import JSONServerSentEvent, EventSourceResponse
import logging

logger = logging.getLogger(__name__)


class SSEPubSub:
    def __init__(self, redis: Redis):
        self._redis = redis

    async def publish(self, channel: str, message: str):
        await self._redis.set(f"prev_{channel}", message)
        await self._redis.publish(channel, message)

    async def get_prev_message(self, channel: str) -> str | None:
        return await self._redis.get(f"prev_{channel}")

    async def subscribe(self, *channels: str):
        """
        订阅频道
        """

        async def _event_generator():
            logger.info(f"subscribe channels: {channels}")
            for channel in channels:
                prev_message = await self.get_prev_message(channel)
                if prev_message:
                    # logger.info(f"get prev message: {prev_message}")
                    yield JSONServerSentEvent(data=prev_message)
            async with self._redis.pubsub() as pubsub:
                await pubsub.subscribe(*channels)
                while True:
                    msg = await pubsub.get_message(
                        ignore_subscribe_messages=True, timeout=0.1
                    )
                    if msg and msg["type"] == "message":
                        # logger.info(f"get message: {msg['data']}")
                        yield JSONServerSentEvent(
                            data=msg["data"],
                        )
                    await asyncio.sleep(0.5)

        return EventSourceResponse(_event_generator())
