"""Message bus abstraction for transform pipeline.

Supports Kafka, Redis Streams, and in-memory queue backends.
Used by services/transform_worker.py for decoupled event ingestion.
"""

from __future__ import annotations

import asyncio
import json
import logging
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from typing import Any, AsyncIterator, Dict, Optional


logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Normalized message format consumed by transform worker."""

    value: Dict[str, Any]
    headers: Dict[str, Any]


class MessageBusAdapter(ABC):
    """Abstract interface for message bus implementations."""

    @abstractmethod
    async def publish(self, topic: str, message: Message) -> None:
        """Publish message to topic/stream."""

    @abstractmethod
    async def subscribe(self, topic: str) -> AsyncIterator[Message]:
        """Yield messages from topic/stream."""

    @abstractmethod
    async def close(self) -> None:
        """Release resources/connections."""


class MemoryAdapter(MessageBusAdapter):
    """In-memory adapter for testing/development."""

    def __init__(self) -> None:
        self._topics: Dict[str, deque[Message]] = {}
        self._conditions: Dict[str, asyncio.Condition] = {}

    def _get_topic(self, topic: str) -> deque[Message]:
        if topic not in self._topics:
            self._topics[topic] = deque()
            self._conditions[topic] = asyncio.Condition()
        return self._topics[topic]

    async def publish(self, topic: str, message: Message) -> None:
        queue = self._get_topic(topic)
        condition = self._conditions[topic]
        async with condition:
            queue.append(message)
            condition.notify()

    async def subscribe(self, topic: str) -> AsyncIterator[Message]:
        queue = self._get_topic(topic)
        condition = self._conditions[topic]
        while True:
            async with condition:
                while not queue:
                    await condition.wait()
                msg = queue.popleft()
            yield msg

    async def close(self) -> None:
        self._topics.clear()
        self._conditions.clear()


class KafkaAdapter(MessageBusAdapter):
    """Kafka adapter using aiokafka."""

    def __init__(self, config: Dict[str, Any]) -> None:
        from aiokafka import AIOKafkaConsumer, AIOKafkaProducer  # type: ignore

        self._config = config
        self._producer = AIOKafkaProducer(
            bootstrap_servers=config["bootstrap_servers"],
            security_protocol=config.get("security_protocol", "PLAINTEXT"),
        )
        self._consumer: Optional[AIOKafkaConsumer] = None

    async def publish(self, topic: str, message: Message) -> None:
        await self._producer.start()
        try:
            headers = [(k, json.dumps(v).encode("utf-8")) for k, v in message.headers.items()]
            await self._producer.send_and_wait(
                topic,
                value=json.dumps(message.value).encode("utf-8"),
                headers=headers,
            )
        finally:
            # Producer remains open for reuse; caller closes via close()
            pass

    async def subscribe(self, topic: str) -> AsyncIterator[Message]:
        from aiokafka import AIOKafkaConsumer  # type: ignore

        if self._consumer is None:
            self._consumer = AIOKafkaConsumer(
                topic,
                bootstrap_servers=self._config["bootstrap_servers"],
                security_protocol=self._config.get("security_protocol", "PLAINTEXT"),
                group_id=self._config.get("group_id"),
                enable_auto_commit=True,
            )
            await self._consumer.start()

        assert self._consumer is not None
        try:
            async for record in self._consumer:
                headers = {
                    key: json.loads(value.decode("utf-8")) if value else None
                    for key, value in (record.headers or [])
                }
                value = json.loads(record.value.decode("utf-8"))
                yield Message(value=value, headers=headers)
        finally:
            await self._consumer.stop()

    async def close(self) -> None:
        await self._producer.stop()
        if self._consumer:
            await self._consumer.stop()
            self._consumer = None


class RedisAdapter(MessageBusAdapter):
    """Redis Streams adapter (uses redis.asyncio)."""

    def __init__(self, config: Dict[str, Any]) -> None:
        import redis.asyncio as redis  # type: ignore

        self._config = config
        self._client = redis.Redis(host=config["host"], port=config.get("port", 6379))

    async def publish(self, topic: str, message: Message) -> None:
        payload = json.dumps({
            "value": message.value,
            "headers": message.headers,
        })
        await self._client.xadd(topic, {"data": payload})

    async def subscribe(self, topic: str) -> AsyncIterator[Message]:
        last_id = "$"
        while True:
            response = await self._client.xread({topic: last_id}, block=1000, count=100)
            if not response:
                continue
            for _, messages in response:
                for msg_id, fields in messages:
                    payload = json.loads(fields[b"data"].decode("utf-8"))
                    last_id = msg_id
                    yield Message(value=payload.get("value", {}), headers=payload.get("headers", {}))

    async def close(self) -> None:
        await self._client.close()


def create_bus_adapter(config: Dict[str, Any]) -> MessageBusAdapter:
    """Factory to create appropriate adapter based on config."""

    bus_type = (config.get("type") or "memory").lower()
    if bus_type == "kafka":
        try:
            logger.info("Initializing Kafka message bus adapter")
            return KafkaAdapter(config.get("kafka", {}))
        except (ImportError, ModuleNotFoundError):
            logger.warning("Kafka not available, falling back to memory adapter")
    if bus_type == "redis":
        try:
            logger.info("Initializing Redis message bus adapter")
            return RedisAdapter(config.get("redis", {}))
        except (ImportError, ModuleNotFoundError):
            logger.warning("Redis not available, falling back to memory adapter")

    logger.info("Initializing in-memory message bus adapter")
    return MemoryAdapter()

