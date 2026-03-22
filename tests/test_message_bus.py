"""Tests for message bus abstraction."""

import asyncio

import pytest

from components.message_bus_adapter import MemoryAdapter, Message


@pytest.mark.asyncio
async def test_memory_adapter_publish_subscribe():
    adapter = MemoryAdapter()

    async def publisher():
        for i in range(3):
            await adapter.publish("test-topic", Message(value={"i": i}, headers={"idx": i}))

    async def consumer():
        received = []
        async for msg in adapter.subscribe("test-topic"):
            received.append(msg.value["i"])
            if len(received) == 3:
                break
        return received

    result = await asyncio.gather(publisher(), consumer())
    assert result[1] == [0, 1, 2]


