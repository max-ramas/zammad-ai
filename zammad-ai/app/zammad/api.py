from logging import Logger
from typing import override

import feedparser
from httpx import AsyncClient, ConnectError, HTTPStatusError, ReadTimeout, Response, TimeoutException
from pydantic import SecretStr, TypeAdapter
from stamina import retry_context

from app.models.zammad import ZammadAnswer, ZammadArticle, ZammadSharedDraft, ZammadSharedDraftArticle, ZammadTagAdd, ZammadTicket
from app.settings.zammad import ZammadAPISettings
from app.utils.logging import getLogger

from .base import BaseZammadClient, ZammadConnectionError

logger: Logger = getLogger("zammad-ai.zammad.api")


class ZammadAPIClient(BaseZammadClient):
    """Client for interacting with Zammad API to fetch and update ticket information."""

    def __init__(self, settings: ZammadAPISettings) -> None:
        """
        Initialize the Zammad API client and store configuration-derived attributes.

        Creates an AsyncClient configured with the settings' base URL, bearer authorization header, and timeout, and saves the knowledge_base_id, rss_feed_token, and max_retries from the provided settings.

        Parameters:
            settings (ZammadAPISettings): Configuration containing base_url, auth_token, timeout, knowledge_base_id, rss_feed_token, and max_retries.
        """
        self.client = AsyncClient(
            base_url=settings.base_url.encoded_string(),
            headers={"Authorization": f"Bearer {settings.auth_token.get_secret_value()}"},  # TODO: implement custom auth schema if needed
            timeout=settings.timeout,
        )
        self.knowledge_base_id: str | None = settings.knowledge_base_id
        self.rss_feed_token: SecretStr | None = settings.rss_feed_token
        self.http_attempts: int = settings.max_retries + 1

    @override
    async def get_ticket(self, id: str) -> ZammadTicket:  # type: ignore
        """
        Fetches a ticket and its articles from Zammad using the ticket ID.

        Parameters:
            id (str): Ticket ID to fetch.

        Returns:
            ZammadTicket: Ticket containing the provided id and the parsed list of articles.

        Raises:
            ZammadConnectionError: If the request fails after retries or an HTTP error occurs.
        """
        try:
            for attempt in retry_context(
                on=(HTTPStatusError, ConnectError, TimeoutException, ReadTimeout),
                attempts=self.http_attempts,
            ):
                with attempt:
                    # Send GET request to Zammad API to fetch ticket information
                    response: Response = await self.client.get(f"/api/v1/ticket_articles/by_ticket/{id}")
                    response.raise_for_status()
                    # Parse the response JSON into a list of ZammadArticle models via a pydantic TypeAdapter
                    ta: TypeAdapter[list[ZammadArticle]] = TypeAdapter(list[ZammadArticle])
                    articles: list[ZammadArticle] = ta.validate_json(response.text)
                    #
                    ticket = ZammadTicket(
                        id=id,
                        articles=articles,
                    )
                    return ticket

        except (HTTPStatusError, ConnectError, TimeoutException, ReadTimeout) as e:
            logger.error(f"Failed to fetch ticket {id} after {self.http_attempts} attempts.", exc_info=True)
            raise ZammadConnectionError(f"Failed to fetch ticket {id} from Zammad after {self.http_attempts} attempts.") from e

    @override
    async def post_answer(
        self,
        ticket_id: str,
        text: str,
        internal: bool = False,
    ) -> None:
        """
        Post an answer to a Zammad ticket.

        Parameters:
            ticket_id (str): ID of the ticket to post the answer to.
            text (str): Content of the answer.
            internal (bool): If True, mark the answer as internal (visible only to agents).

        Raises:
            ZammadConnectionError: If posting the article fails after retrying.
        """
        article_payload = ZammadAnswer(
            ticket_id=ticket_id,
            body=text,
            internal=internal,
        )

        try:
            for attempt in retry_context(
                on=(HTTPStatusError, ConnectError, TimeoutException, ReadTimeout),
                attempts=self.http_attempts,
            ):
                with attempt:
                    response: Response = await self.client.post(
                        url="/api/v1/ticket_articles",
                        json=article_payload.model_dump(),
                    )
                    response.raise_for_status()
                    logger.info(f"Successfully posted answer to ticket {ticket_id}.")
                    return
        except (HTTPStatusError, ConnectError, TimeoutException, ReadTimeout) as e:
            logger.error(f"Failed to post answer to ticket {ticket_id} after {self.http_attempts} attempts.", exc_info=True)
            raise ZammadConnectionError(f"Failed to post answer to ticket {ticket_id} after {self.http_attempts} attempts.") from e

    @override
    async def post_shared_draft(
        self,
        ticket_id: str,
        text: str,
    ) -> None:
        """
        Create a shared draft (internal note) on a Zammad ticket.

        Raises:
            ZammadConnectionError: If posting fails after the configured retry attempts or if Zammad returns an HTTP error.
        """
        payload = ZammadSharedDraft(
            new_article=ZammadSharedDraftArticle(
                body=text,
                ticket_id=ticket_id,
            ),
        )

        try:
            for attempt in retry_context(
                on=(HTTPStatusError, ConnectError, TimeoutException, ReadTimeout),
                attempts=self.http_attempts,
            ):
                with attempt:
                    response: Response = await self.client.put(
                        url=f"/api/v1/tickets/{ticket_id}/shared_draft",
                        json=payload.model_dump(by_alias=True),
                    )
                    response.raise_for_status()
                    logger.info(f"Successfully posted shared draft to ticket {ticket_id}.")
                    return
        except (HTTPStatusError, ConnectError, TimeoutException, ReadTimeout) as e:
            logger.error(f"Failed to post shared draft to ticket {ticket_id} after {self.http_attempts} attempts.", exc_info=True)
            raise ZammadConnectionError(f"Failed to post shared draft to ticket {ticket_id} after {self.http_attempts} attempts.") from e

    @override
    async def add_tag_to_ticket(self, ticket_id: str, tag: str) -> None:
        """
        Add a tag to the specified Zammad ticket.
        
        Performs an API request to add the given tag; if the request repeatedly fails due to HTTP or connection errors, a ZammadConnectionError is raised.
        
        Parameters:
            ticket_id (str): ID of the ticket to update.
            tag (str): Tag to add.
        
        Raises:
            ZammadConnectionError: If adding the tag fails after retrying the configured number of attempts.
        """
        payload = ZammadTagAdd(
            item=tag,
            o_id=ticket_id,
        )
        try:
            for attempt in retry_context(
                on=(HTTPStatusError, ConnectError, TimeoutException, ReadTimeout),
                attempts=self.http_attempts,
            ):
                with attempt:
                    response: Response = await self.client.post(
                        url="/api/v1/tags/add",
                        json=payload.model_dump(),
                    )
                    response.raise_for_status()
                    logger.info(f"Successfully added tag '{tag}' to ticket {ticket_id}.")
                    return
        except (HTTPStatusError, ConnectError, TimeoutException, ReadTimeout) as e:
            logger.error(f"Failed to add tag '{tag}' to ticket {ticket_id} after {self.http_attempts} attempts.", exc_info=True)
            raise ZammadConnectionError(f"Failed to add tag '{tag}' to ticket {ticket_id} after {self.http_attempts} attempts.") from e

    async def parse_rss_feed(self) -> feedparser.FeedParserDict | None:
        """
        Fetch and parse the knowledge base RSS feed.
        
        Returns:
            feedparser.FeedParserDict: Parsed feed when fetched successfully, or `None` if the knowledge base ID or RSS feed token is not configured.
        
        Raises:
            ZammadConnectionError: If fetching the RSS feed fails after the configured retry attempts.
        """
        if not self.knowledge_base_id or not self.rss_feed_token:
            logger.error("Knowledge base ID or RSS feed token not configured")
            return None

        feed_url = f"/api/v1/knowledge_bases/{self.knowledge_base_id}/de-de/feed?token={self.rss_feed_token.get_secret_value()}"

        try:
            for attempt in retry_context(
                on=(HTTPStatusError, ConnectError, TimeoutException, ReadTimeout),
                attempts=self.http_attempts,
            ):
                with attempt:
                    response: Response = await self.client.get(feed_url)
                    response.raise_for_status()
                    # Parse RSS feed content using feedparser
                    feed = feedparser.parse(response.text)
                    if getattr(feed, "bozo", False):
                        logger.warning("Feed may have issues: %s", getattr(feed, "bozo_exception", "unknown"))
                    return feed
        except (HTTPStatusError, ConnectError, TimeoutException, ReadTimeout) as e:
            logger.error("Failed to fetch RSS feed after %s attempts.", self.http_attempts, exc_info=True)
            raise ZammadConnectionError(f"Failed to fetch RSS feed after {self.http_attempts} attempts.") from e

    async def get_kb_answer_by_id(self, answer_id: str) -> dict | None:
        """
        Fetch a knowledge base answer by ID.
        
        Returns:
            dict: The answer JSON if found, `None` if the answer does not exist (HTTP 404).
        
        Raises:
            ZammadConnectionError: If the request fails after retries for reasons other than a 404.
        """
        if not self.knowledge_base_id:
            logger.error("Knowledge base ID not configured")
            return None

        url = f"/api/v1/knowledge_bases/{self.knowledge_base_id}/answers/{answer_id}?include_contents={answer_id}"

        try:
            for attempt in retry_context(
                on=(HTTPStatusError, ConnectError, TimeoutException, ReadTimeout),
                attempts=self.http_attempts,
            ):
                with attempt:
                    response: Response = await self.client.get(url)
                    response.raise_for_status()
                    logger.info(f"Successfully fetched KB answer {answer_id}.")
                    return response.json()
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                logger.warning(f"KB answer {answer_id} not found (404).")
                return None
            logger.error(f"KB answer fetch failed ({e.response.status_code}) for {answer_id}.", exc_info=True)
            raise ZammadConnectionError(f"Failed to fetch KB answer {answer_id} after {self.http_attempts} attempts.") from e
        except (ConnectError, TimeoutException, ReadTimeout) as e:
            logger.error(f"Failed to fetch KB answer {answer_id} after {self.http_attempts} attempts.", exc_info=True)
            raise ZammadConnectionError(f"Failed to fetch KB answer {answer_id} after {self.http_attempts} attempts.") from e

    async def fetch_attachment_data(self, url: str) -> str | None:
        """
        Retrieve an attachment and return its textual content or a base64-encoded string for binary data.
        
        Parameters:
            url (str): Relative URL of the attachment to fetch.
        
        Returns:
            str: Decoded text for responses with Content-Type starting with `application/json` or `text/`; a base64-encoded ASCII string for other (binary) content. `None` if `url` is falsy.
        
        Raises:
            ZammadConnectionError: If the attachment could not be fetched after the configured retry attempts.
        """
        if not url:
            logger.warning("No URL provided for attachment fetch")
            return None

        try:
            for attempt in retry_context(
                on=(HTTPStatusError, ConnectError, TimeoutException, ReadTimeout),
                attempts=self.http_attempts,
            ):
                with attempt:
                    response: Response = await self.client.get(url)
                    response.raise_for_status()
                    # Decode response content
                    content_type = (response.headers.get("Content-Type") or "").lower()
                    if content_type.startswith("application/json") or content_type.startswith("text/"):
                        return response.text
                    else:
                        import base64

                        return base64.b64encode(response.content).decode("ascii")
        except (HTTPStatusError, ConnectError, TimeoutException, ReadTimeout) as e:
            logger.error(f"Failed to fetch attachment from {url} after {self.http_attempts} attempts.", exc_info=True)
            raise ZammadConnectionError(f"Failed to fetch attachment from {url} after {self.http_attempts} attempts.") from e

    async def check_if_answer_exists(self, answer_id: str) -> bool:
        """
        Determine whether a knowledge base answer with the given ID exists.
        
        Returns:
            `true` if the answer exists, `false` if it was not found (HTTP 404).
        
        Raises:
            ZammadConnectionError: If the request fails for reasons other than the answer being missing.
        """
        if not self.knowledge_base_id:
            logger.error("Knowledge base ID not configured")
            return False

        url = f"/api/v1/knowledge_bases/{self.knowledge_base_id}/answers/{answer_id}?include_contents={answer_id}"

        try:
            response: Response = await self.client.get(url)
            response.raise_for_status()
            return True
        except HTTPStatusError as e:
            if e.response.status_code == 404:
                return False
            logger.error(f"Error checking KB answer {answer_id}.", exc_info=True)
            raise ZammadConnectionError(f"Failed to check KB answer {answer_id}.") from e
        except (ConnectError, TimeoutException, ReadTimeout) as e:
            logger.error(f"Error checking KB answer {answer_id}.", exc_info=True)
            raise ZammadConnectionError(f"Failed to check KB answer {answer_id}.") from e

    @override
    async def cleanup(self) -> None:
        """
        Close the httpx client.
        """
        await self.client.aclose()
        logger.info("Zammad API client closed.")
