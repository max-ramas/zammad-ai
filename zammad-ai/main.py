# ruff: noqa: E402
from logging import Logger

from dotenv import load_dotenv
from faststream import FastStream
from faststream.kafka import KafkaBroker
from truststore import inject_into_ssl

load_dotenv()
inject_into_ssl()

import asyncio

from app.core.settings import Settings, get_settings
from app.kafka.broker import build_broker
from app.utils.logging import getLogger


async def main() -> None:
    """Runs the application."""
    logger: Logger = getLogger("zammad-ai")
    logger.info("Starting application")
    settings: Settings = get_settings()
    broker: KafkaBroker
    broker, _ = build_broker(settings=settings)
    app = FastStream(broker)
    logger.info("Running FastStream application")
    await app.run()  # blocking method


if __name__ == "__main__":
    asyncio.run(main())
