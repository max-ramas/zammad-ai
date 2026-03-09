from app.models.triage import CategorizationResult, DaysSinceRequestResponse, ProcessingIdResponse
from app.models.zammad import ZammadTicket
from app.settings import GenAISettings
from app.settings.zammad import ZammadAPISettings


class FakeZammadConnectionError(Exception):
    pass


class FakeLangfuseClient:
    def generate_session_id(self) -> str:
        return "session-id"


class FakeGenAIHandler:
    def __init__(self, genai_settings: GenAISettings, prompts: dict[str, str]) -> None:
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
        self.settings = settings
        self.ticket: ZammadTicket | None = None
        self.raise_connection_error: bool = False

    async def get_ticket(self, id: str) -> ZammadTicket:
        if self.raise_connection_error:
            raise FakeZammadConnectionError("Fake connection error")
        if self.ticket is None:
            return ZammadTicket(id=id, articles=[])
        return self.ticket

    async def post_answer(self, ticket_id: str, text: str, internal: bool = False) -> None:
        raise AssertionError("post_answer should not be called in these tests")

    async def post_shared_draft(self, ticket_id: str, text: str) -> None:
        raise AssertionError("post_shared_draft should not be called in these tests")

    async def add_tag_to_ticket(self, ticket_id: str, tag: str) -> None:
        raise AssertionError("add_tag_to_ticket should not be called in these tests")

    async def cleanup(self) -> None:
        return None

    async def parse_rss_feed(self) -> dict | None:
        raise AssertionError("parse_rss_feed should not be called in these tests")

    async def get_kb_answer_by_id(self, answer_id: str) -> dict | None:
        raise AssertionError("get_kb_answer_by_id should not be called in these tests")

    async def fetch_attachment_data(self, url: str) -> str | None:
        raise AssertionError("fetch_attachment_data should not be called in these tests")

    async def check_if_answer_exists(self, answer_id: str) -> bool:
        raise AssertionError("check_if_answer_exists should not be called in these tests")
