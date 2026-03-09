from logging import Logger

import gradio as gr
from fastapi import FastAPI

from app.settings import FrontendSettings
from app.utils.logging import getLogger

from .ui import build_frontend

logger: Logger = getLogger("zammad-ai.frontend.integration")


def mount_frontend(app: FastAPI, frontend_settings: FrontendSettings) -> FastAPI:
    """Mount the Gradio frontend on `/` if enabled."""
    if not frontend_settings.enabled:
        return app

    auth: tuple[str, str] = (
        frontend_settings.auth_username.get_secret_value(),
        frontend_settings.auth_password.get_secret_value(),
    )

    logger.info("Mounting frontend on root path.")
    frontend = build_frontend(frontend_settings=frontend_settings)

    return gr.mount_gradio_app(
        app=app,
        blocks=frontend,
        path="",
        auth=auth,
    )
