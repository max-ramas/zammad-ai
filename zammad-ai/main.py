# ruff: noqa: E402
from dotenv import load_dotenv
from truststore import inject_into_ssl

load_dotenv()
inject_into_ssl()

import asyncio

from app.broker.kafka import app
from app.core.settings import Settings, get_settings


async def main() -> None:
    _: Settings = get_settings()
    await app.run()  # blocking method


if __name__ == "__main__":
    asyncio.run(main())
