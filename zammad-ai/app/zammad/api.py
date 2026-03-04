from logging import Logger
from typing import override

import feedparser
from pydantic import TypeAdapter

from app.core.settings.zammad import ZammadAPISettings
from app.models.zammad import ZammadAnswer, ZammadArticle, ZammadSharedDraftAPI, ZammadSharedDraftArticle, ZammadTagAdd, ZammadTicket
from app.utils.logging import getLogger

from .base import BaseZammadClient

logger: Logger = getLogger("zammad-ai.zammad.api")


class ZammadAPIClient(BaseZammadClient):
    """Client for interacting with Zammad API to fetch and update ticket information."""

    def __init__(self, settings: ZammadAPISettings):
        super().__init__(base_url=settings.base_url.encoded_string(), timeout=settings.timeout, max_retries=settings.max_retries)

        # Set auth header
        self.client.headers.update({"Authorization": f"Bearer {settings.auth_token.get_secret_value()}"})

        self.kb_id = settings.knowledge_base_id
        self.rss_token = settings.rss_feed_token

    @override
    async def get_ticket(self, id: str) -> ZammadTicket:
        data = await self._request("GET", f"/api/v1/ticket_articles/by_ticket/{id}")
        articles = TypeAdapter(list[ZammadArticle]).validate_python(data)
        return ZammadTicket(id=id, articles=articles)

    @override
    async def post_answer(self, ticket_id: str, text: str, subject: str | None = None, internal: bool = False) -> None:
        payload = ZammadAnswer(ticket_id=ticket_id, body=text, internal=internal, subject=subject)
        await self._request("POST", "/api/v1/ticket_articles", json=payload.model_dump())
        logger.info(f"Posted answer to ticket {ticket_id}")

    @override
    async def post_shared_draft(self, ticket_id: str, text: str) -> None:
        payload = ZammadSharedDraftAPI(new_article=ZammadSharedDraftArticle(body=text, ticket_id=ticket_id))
        await self._request("PUT", f"/api/v1/tickets/{ticket_id}/shared_draft", json=payload.model_dump(by_alias=True))
        logger.info(f"Posted shared draft to ticket {ticket_id}")

    @override
    async def add_tag_to_ticket(self, ticket_id: str, tag: str) -> None:
        payload = ZammadTagAdd(item=tag, o_id=ticket_id)
        await self._request("POST", "/api/v1/tags/add", json=payload.model_dump())
        logger.info(f"Added tag '{tag}' to ticket {ticket_id}")

    @override
    async def parse_rss_feed(self) -> feedparser.FeedParserDict | None:
        if not self.kb_id or not self.rss_token:
            return None

        url = f"/api/v1/knowledge_bases/{self.kb_id}/de-de/feed?token={self.rss_token.get_secret_value()}"
        text = await self._request("GET", url)
        return feedparser.parse(text)

    @override
    async def get_kb_answer_by_id(self, answer_id: str) -> dict | None:
        if not self.kb_id:
            return None

        try:
            return await self._request("GET", f"/api/v1/knowledge_bases/{self.kb_id}/answers/{answer_id}?include_contents={answer_id}")
        except Exception:
            return None

    @override
    async def fetch_attachment_data(self, url: str) -> str | None:
        return await self._request("GET", url) if url else None

    @override
    async def check_if_answer_exists(self, answer_id: str) -> bool:
        try:
            await self.get_kb_answer_by_id(answer_id)
            return True
        except Exception:
            return False
