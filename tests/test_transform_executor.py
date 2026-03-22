"""Tests for transform executor strategies."""

import pytest

from components.transform_executor import LupaExecutor


@pytest.mark.asyncio
async def test_lupa_executor_simple():
    executor = LupaExecutor()
    lua_code = """
function processEvent(event)
  event.result = event.value * 2
  return event
end
"""

    success, result = await executor.execute(lua_code, {"value": 5}, "parser-1")
    assert success
    assert result["result"] == 10


