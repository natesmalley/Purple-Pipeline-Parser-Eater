"""CLI entrypoint for transform worker."""

import asyncio
import logging


from services.transform_worker import TransformWorker
from utils.config import load_config
from services.runtime_service import RuntimeService


async def main() -> None:
    config = load_config()
    runtime_service = RuntimeService()
    worker = TransformWorker(config, runtime_service=runtime_service)
    try:
        await worker.run()
    finally:
        await worker.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())

