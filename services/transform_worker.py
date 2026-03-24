"""Transform worker service for runtime event processing."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict

from components.message_bus_adapter import Message, create_bus_adapter
from components.transform_executor import create_executor
from components.manifest_store import ManifestStore
from components.canary_router import CanaryRouter
from components.runtime_metrics import RuntimeMetricsStore


logger = logging.getLogger(__name__)


class TransformWorker:
    """Consumes events, applies Lua transforms, publishes results."""

    def __init__(self, config: Dict[str, Any], runtime_service=None) -> None:
        self.config = config
        self.bus = create_bus_adapter(config.get("message_bus", {}))
        self.executor = create_executor(config)
        self.manifest_store = ManifestStore()
        canary_config = config.get("canary", {})
        promotion_threshold = canary_config.get("promotion_threshold", 1000)
        error_tolerance = canary_config.get("error_tolerance", 0.01)
        self.canary_router = CanaryRouter(
            promotion_threshold=promotion_threshold,
            error_tolerance=error_tolerance,
        )
        self.runtime_metrics = RuntimeMetricsStore()
        self.runtime_service = runtime_service
        self.input_topic = config.get("transform_worker", {}).get("input_topic", "raw-security-events")
        self.output_topic = config.get("transform_worker", {}).get("output_topic", "ocsf-events")

    async def run(self) -> None:
        logger.info("Transform worker listening on topic %s", self.input_topic)
        async for message in self.bus.subscribe(self.input_topic):
            await self._handle_message(message)

    async def _handle_message(self, message: Message) -> None:
        parser_id = message.headers.get("parser_id", "unknown")
        lua_code = message.headers.get("lua_code")
        manifest = self.manifest_store.load_manifest(parser_id, "stable")
        canary_manifest = self.manifest_store.load_manifest(parser_id, "canary")

        self.canary_router.register(parser_id, manifest, "stable")
        self.canary_router.register(parser_id, canary_manifest, "canary")

        try:
            version_mode, selection = self.canary_router.select(
                parser_id,
                hash(message.value.get("id", parser_id))
            )
        except (KeyError, ValueError) as exc:
            logger.error("No manifest available for %s: %s", parser_id, exc)
            return

        lua_filename = selection.lua_metadata.file if selection.lua_metadata else "transform.lua"
        lua_source = self.manifest_store.load_lua(parser_id, lua_filename)
        if not lua_source:
            logger.error("Lua code not found for %s (file %s)", parser_id, lua_filename)
            return

        success, result = await self.executor.execute(lua_source, message.value, parser_id)
        is_canary = version_mode == "canary"
        self.canary_router.record(
            parser_id,
            selection.version.semantic,
            success,
            is_canary,
            result.get("error") if not success else None,
        )
        runtime_metric = self.runtime_metrics.for_parser(parser_id)
        runtime_metric.record(success, is_canary, result.get("error") if not success else None)
        if self.runtime_service:
            self.runtime_service.update_metrics({parser_id: runtime_metric.to_dict()})
            if self.runtime_service.pending_promotions.get(parser_id) == "pending":
                if self.canary_router.should_promote_canary(parser_id):
                    self.runtime_service.pending_promotions[parser_id] = "ready"

        if not success:
            logger.error("Transform failed for %s: %s", parser_id, result.get("error"))
            return

        await self.bus.publish(
            self.output_topic,
            Message(value=result, headers={"parser_id": parser_id})
        )

    async def close(self) -> None:
        await self.executor.close()
        await self.bus.close()


async def main() -> None:
    from utils.config import load_config  # type: ignore

    config = load_config()
    worker = TransformWorker(config)
    try:
        await worker.run()
    finally:
        await worker.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

