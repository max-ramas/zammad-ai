from base64 import b64decode
from datetime import datetime, timedelta
from logging import Logger
from typing import Any, override

from feedparser import FeedParserDict
from feedparser import parse as feedparser
from pydantic import TypeAdapter

from app.core.settings.zammad import ZammadEAISettings
from app.models.zammad import KnowledgeBaseAnswer, ZammadAnswer, ZammadArticle, ZammadKnowledgebase, ZammadSharedDraftEAI, ZammadTicket
from app.utils.logging import getLogger

from .base import BaseZammadClient

logger: Logger = getLogger("zammad-ai.zammad.eai")


class ZammadEAIClient(BaseZammadClient):
    """Zammad EAI client implementation for Zammad AI with OAuth 2.0 support."""

    def __init__(self, settings: ZammadEAISettings):
        super().__init__(
            base_url=settings.eai_url.encoded_string(),
            timeout=settings.timeout,
            max_retries=settings.max_retries,
            proxy_url=settings.proxy_url,
        )

        self.settings = settings
        self.kb_id = settings.knowledge_base_id
        self._token = None
        self._token_expires = None

    async def _ensure_auth(self) -> None:
        """Ensure OAuth token is valid."""
        if self._token and self._token_expires and datetime.now() < self._token_expires - timedelta(minutes=5):
            return

        # Get new token
        token_data = {
            "grant_type": "client_credentials",
            "client_id": self.settings.client_id,
            "client_secret": self.settings.client_secret.get_secret_value(),
        }
        if self.settings.scope:
            token_data["scope"] = self.settings.scope

        response = await self.client.post(
            str(self.settings.token_url), data=token_data, headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        response.raise_for_status()

        token_resp = response.json()
        self._token = token_resp["access_token"]
        expires_in = token_resp.get("expires_in", 3600)
        self._token_expires = datetime.now() + timedelta(seconds=expires_in)

    async def _request(self, method: str, url: str, **kwargs) -> Any:
        """Make authenticated request."""
        await self._ensure_auth()

        headers = kwargs.get("headers", {})
        headers["Authorization"] = f"Bearer {self._token}"
        kwargs["headers"] = headers

        return await super()._request(method, url, **kwargs)

    @override
    async def get_ticket(self, id: str) -> ZammadTicket:
        data = await self._request("GET", f"/tickets/byId/{id}")
        articles = TypeAdapter(list[ZammadArticle]).validate_python(data["articles"])
        return ZammadTicket(id=id, articles=articles)

    @override
    async def post_answer(self, ticket_id: str, text: str, subject: str | None = None, internal: bool = False) -> None:
        payload = ZammadAnswer(ticket_id=ticket_id, body=text, internal=internal, subject=subject)
        await self._request("POST", f"/tickets/{ticket_id}/articles", json=payload.model_dump())
        logger.info(f"Posted answer to ticket {ticket_id}")

    @override
    async def post_shared_draft(self, ticket_id: str, text: str) -> None:
        payload = ZammadSharedDraftEAI(body=text)
        await self._request("PUT", f"/tickets/{ticket_id}/shared_draft", json=payload.model_dump())
        logger.info(f"Posted shared draft to ticket {ticket_id}")

    @override
    async def add_tag_to_ticket(self, ticket_id: str, tag: str) -> None:
        raise NotImplementedError("Adding tag is not implemented yet.")

    @override
    async def show_kb(self) -> ZammadKnowledgebase | None:
        if not self.kb_id:
            return None

        data = await self._request("GET", f"/knowledgeBases/{self.kb_id}")
        return TypeAdapter(ZammadKnowledgebase).validate_python(data) if data else None

    @override
    async def parse_rss_feed(self) -> FeedParserDict | None:
        if not self.kb_id:
            return None

        response = await self._request("GET", f"/knowledgeBases/{self.kb_id}/rss")

        try:
            # If it's Base64-encoded XML, decode it
            import base64

            text = base64.b64decode(response).decode("utf-8")
        except Exception:
            # If decoding fails, assume it's already plain text
            text = response

        return feedparser(text)

    @override
    async def get_kb_answer_by_id(self, answer_id: str) -> KnowledgeBaseAnswer | None:
        if not self.kb_id:
            return None

        try:
            response = await self._request("GET", f"/knowledgeBases/{self.kb_id}/answer/{answer_id}")
            return TypeAdapter(KnowledgeBaseAnswer).validate_python(response)
        except Exception:
            logger.warning(f"Failed to get knowledge base answer {answer_id}", exc_info=True)
            return None

    @override
    async def fetch_kb_attachment_data(self, id: str) -> str | None:
        data = await self._request("GET", f"/attachments/{id}") if id else None
        return b64decode(data).decode("utf-8") if id and data else None

    @override
    async def fetch_ticket_attachment_data(self, ticket_id: str, attachment_id: str, article_id: str) -> str | None:
        data = (
            await self._request("GET", f"/attachments/{ticket_id}/{article_id}/{attachment_id}")
            if ticket_id and attachment_id and article_id
            else None
        )
        return b64decode(data).decode("utf-8") if data else None

    @override
    async def check_if_answer_exists(self, answer_id: str) -> bool:
        answer: KnowledgeBaseAnswer | None = await self.get_kb_answer_by_id(answer_id)
        return answer is not None

    @override
    async def cleanup(self) -> None:
        """Cleanup tokens and close client."""
        self._token = None
        self._token_expires = None
        await super().cleanup()
