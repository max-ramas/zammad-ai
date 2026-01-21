# ruff: noqa: E402

import argparse

from dotenv import load_dotenv
from truststore import inject_into_ssl

load_dotenv()
inject_into_ssl()

import uvicorn

from app.utils.logging import getLogger

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--development", action="store_true")
    args = parser.parse_args()

    logger = getLogger()
    logger.info("Starting Zammad AI Backend")

    uvicorn.run("app.core.backend:backend", host="localhost", port=8080, log_config="logconf.yaml")
