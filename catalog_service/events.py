import json
import logging
from collections.abc import AsyncIterator

import redis
import redis.asyncio

from . import config

logger = logging.getLogger(__name__)

# Every catalog instance publishes and subscribes here, so a browser connected to
# one instance still hears about changes made through the other.
CHANNEL = "catalog:events"

_publisher = redis.Redis.from_url(config.REDIS_URL)


def publish(action: str, video_id: int) -> None:
    """Tell open pages that a video changed. Best effort: a missed event only
    means a page shows stale data until it next reloads."""
    try:
        _publisher.publish(CHANNEL, json.dumps({"action": action, "video_id": video_id}))
    except redis.RedisError as exc:
        logger.warning("Could not publish %s event for video %s: %s", action, video_id, exc)


async def subscribe() -> AsyncIterator[dict]:
    # No socket timeout: this connection is expected to sit idle between events.
    client = redis.asyncio.Redis.from_url(config.REDIS_URL, decode_responses=True, socket_timeout=None)
    try:
        async with client.pubsub() as pubsub:
            await pubsub.subscribe(CHANNEL)
            async for message in pubsub.listen():
                if message["type"] == "message":
                    yield json.loads(message["data"])
    finally:
        await client.aclose()
