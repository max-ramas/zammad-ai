from app.models.triage import CategorizationResult, DaysSinceRequestResponse, ProcessingIdResponse
from app.models.zammad import ZammadTicket
from app.settings import GenAISettings
from app.settings.zammad import ZammadAPISettings


class FakeZammadConnectionError(Exception):
    pass


class FakeLangfuseClient:
    def generate_session_id(self) -> str:
        """
        Produce a fixed session identifier used by tests.
        
        Returns:
            session_id (str): The constant string "session-id".
        """
        return "session-id"


class FakeGenAIHandler:
    def __init__(self, genai_settings: GenAISettings, prompts: dict[str, str]) -> None:
        """
        Initialize a test double for GenAI interactions.
        
        Creates a FakeLangfuseClient, stores the provided prompt templates, and initializes injectable result placeholders used by tests.
        
        Parameters:
            genai_settings (GenAISettings): Settings object accepted for API compatibility; not retained by the fake.
            prompts (dict[str, str]): Mapping of prompt keys to prompt templates used by the fake handler.
        """
        self.prompts = prompts
        self.langfuse_client = FakeLangfuseClient()
        self.categorization_result: CategorizationResult | None = None
        self.days_since_request_response: DaysSinceRequestResponse | None = None
        self.processing_id_response: ProcessingIdResponse | None = None

    async def invoke(
        self,
        prompt_key: str,
        input: dict,
        *,
        session_id: str | None = None,
        schema: type | None = None,
    ) -> CategorizationResult | DaysSinceRequestResponse | ProcessingIdResponse | dict:
        """
        Return a canned GenAI response matching the requested schema for testing.
        
        Parameters:
        	prompt_key (str): Identifier for the prompt template to invoke.
        	input (dict): Input payload provided to the handler.
        	schema (type | None): If set, selects which fake response type to return.
        
        Returns:
        	A CategorizationResult when `schema` is `CategorizationResult` (defaults to `category=None, reasoning="no result", confidence=0.0` if no override is set); a DaysSinceRequestResponse when `schema` is `DaysSinceRequestResponse` (defaults to `days_since_request=0, reason="default"` if no override is set); a ProcessingIdResponse when `schema` is `ProcessingIdResponse` (defaults to `processing_id="", condition_met=False` if no override is set); otherwise an empty dict.
        """
        if schema == CategorizationResult:
            if self.categorization_result is None:
                return CategorizationResult(
                    category=None,
                    reasoning="no result",
                    confidence=0.0,
                )
            return self.categorization_result
        if schema == DaysSinceRequestResponse:
            if self.days_since_request_response is None:
                return DaysSinceRequestResponse(days_since_request=0, reason="default")
            return self.days_since_request_response
        if schema == ProcessingIdResponse:
            if self.processing_id_response is None:
                return ProcessingIdResponse(processing_id="", condition_met=False)
            return self.processing_id_response
        return {}


class FakeZammadClient:
    def __init__(self, settings: ZammadAPISettings) -> None:
        """
        Create a fake Zammad client configured for tests.
        
        Parameters:
            settings (ZammadAPISettings): Configuration used by the fake client; stored on the instance.
        
        The instance initializes `ticket` to None and `raise_connection_error` to False to allow tests to inject a ticket or simulate a connection error.
        """
        self.settings = settings
        self.ticket: ZammadTicket | None = None
        self.raise_connection_error: bool = False

    async def get_ticket(self, id: str) -> ZammadTicket:
        """
        Retrieve a ticket by id, raising a fake connection error when configured.
        
        If a preset ticket has been assigned to the fake client, that ticket is returned.
        Otherwise returns a new ZammadTicket with the given `id` and an empty `articles` list.
        
        Parameters:
            id (str): The ticket identifier to fetch.
        
        Returns:
            ZammadTicket: The fetched or default ticket for the given `id`.
        
        Raises:
            FakeZammadConnectionError: If the client is configured to simulate a connection error.
        """
        if self.raise_connection_error:
            raise FakeZammadConnectionError("Fake connection error")
        if self.ticket is None:
            return ZammadTicket(id=id, articles=[])
        return self.ticket

    async def post_answer(self, ticket_id: str, text: str, internal: bool = False) -> None:
        """
        Prevent posting an answer during tests by failing if called.
        
        Raises:
            AssertionError: Always raised to indicate this method must not be invoked in tests.
        """
        raise AssertionError("post_answer should not be called in these tests")

    async def post_shared_draft(self, ticket_id: str, text: str) -> None:
        """
        Signal that posting a shared draft is unsupported by this fake client and fail the test if invoked.
        
        Raises:
            AssertionError: Always raised to indicate this method must not be called in tests.
        """
        raise AssertionError("post_shared_draft should not be called in these tests")

    async def add_tag_to_ticket(self, ticket_id: str, tag: str) -> None:
        """
        Prevent accidental use of tag-adding in tests by failing immediately.
        
        Raises:
            AssertionError: Always raised to indicate this fake client must not be asked to add a tag to a ticket during tests.
        """
        raise AssertionError("add_tag_to_ticket should not be called in these tests")

    async def cleanup(self) -> None:
        """
        Perform cleanup for the fake client.
        
        This implementation performs no action.
        """
        return None

    async def parse_rss_feed(self) -> dict | None:
        """
        Stub method that must not be called during tests and signals misuse by raising an AssertionError.
        
        @raises AssertionError: always raised with message "parse_rss_feed should not be called in these tests"
        """
        raise AssertionError("parse_rss_feed should not be called in these tests")

    async def get_kb_answer_by_id(self, answer_id: str) -> dict | None:
        raise AssertionError("get_kb_answer_by_id should not be called in these tests")

    async def fetch_attachment_data(self, url: str) -> str | None:
        """
        Fail the test if code attempts to fetch attachment data from a URL.
        
        Raises:
            AssertionError: Always raised with message "fetch_attachment_data should not be called in these tests".
        """
        raise AssertionError("fetch_attachment_data should not be called in these tests")

    async def check_if_answer_exists(self, answer_id: str) -> bool:
        """
        Indicates whether a knowledge-base answer exists for the given answer ID.
        
        Parameters:
            answer_id (str): The identifier of the knowledge-base answer to check.
        
        Returns:
            `true` if an answer with the given ID exists, `false` otherwise.
        
        Raises:
            AssertionError: Always raised in this fake implementation with the message
            "check_if_answer_exists should not be called in these tests".
        """
        raise AssertionError("check_if_answer_exists should not be called in these tests")
