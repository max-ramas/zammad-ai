# ruff: noqa: E402
from dotenv import load_dotenv
from truststore import inject_into_ssl

load_dotenv()
inject_into_ssl()


from logging import Logger

import uvicorn

from app.api.backend import backend
from app.core.settings import ZammadAISettings, get_settings
from app.utils.logging import get_log_config, getLogger

if __name__ == "__main__":
    logger: Logger = getLogger()
    settings: ZammadAISettings = get_settings()
    logger.info(msg="Starting Zammad AI Backend")

    if settings.mode == "unittest":
        logger.error(msg="Zammad AI cannot be started in unittest mode.")
        exit(code=1)

    hosts: dict[str, str] = {
        "development": "localhost",
        "production": "0.0.0.0",
    }

    uvicorn.run(app=backend, host=hosts[settings.mode], port=8080, log_config=get_log_config())
