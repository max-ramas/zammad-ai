import html
import re
from datetime import datetime

from pydantic import AliasChoices, BaseModel, Field, field_validator


class ZammadKnowledgebase(BaseModel):
    id: int = Field(
        description="ID of the knowledge base",
    )
    active: bool = Field(
        description="Whether the knowledge base is active",
        default=True,
    )
    createdAt: str = Field(
        description="Creation timestamp of the knowledge base",
    )
    updatedAt: str = Field(
        description="Last update timestamp of the knowledge base",
    )
    categoryIds: list[int] = Field(
        description="List of category IDs associated with the knowledge base",
        default_factory=list,
    )
    answerIds: list[int] = Field(
        description="List of answer IDs associated with the knowledge base",
        default_factory=list,
    )

    @field_validator("createdAt", "updatedAt", mode="before")
    @classmethod
    def validate_timestamps(cls, value: str) -> str:
        """Cast timestamp to ISO 8601 format (YYYY-MM-DDTHH:MM:SSZ)."""
        # If already in correct format, return as-is
        iso8601_pattern = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"
        if re.match(iso8601_pattern, value):
            return value

        # Common timestamp formats to try parsing
        formats_to_try = [
            "%Y-%m-%dT%H:%M:%S",  # 2024-01-01T12:00:00
            "%Y-%m-%dT%H:%M:%S.%f",  # 2024-01-01T12:00:00.123456
            "%Y-%m-%dT%H:%M:%S.%fZ",  # 2024-01-01T12:00:00.123456Z
            "%Y-%m-%d %H:%M:%S",  # 2024-01-01 12:00:00
            "%Y-%m-%d",  # 2024-01-01
            "%d/%m/%Y %H:%M:%S",  # 01/01/2024 12:00:00
            "%d/%m/%Y",  # 01/01/2024
            "%d.%m.%Y %H:%M:%S",  # 01.01.2024 12:00:00
            "%d.%m.%Y",  # 01.01.2024
        ]

        # Try to parse and convert to ISO 8601
        for fmt in formats_to_try:
            try:
                dt = datetime.strptime(value, fmt)
                return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                continue

        # If no format matched, raise error
        raise ValueError(f"Timestamp '{value}' could not be parsed to ISO 8601 format.")


class KnowledgeBaseAttachment(BaseModel):
    id: int = Field(
        description="ID of the attachment",
    )
    filename: str = Field(
        description="Filename of the attachment",
    )
    contentType: str = Field(
        description="Content type of the attachment",
    )


class KnowledgeBaseAnswer(BaseModel):
    id: int = Field(
        description="The ID of the answer",
    )
    answerTitle: str = Field(
        description="The title of the answer",
    )
    answerBody: str = Field(
        description="The content of the answer",
    )
    createdAt: str = Field(
        description="The creation timestamp of the answer",
    )
    updatedAt: str = Field(
        description="The last update timestamp of the answer",
    )
    attachments: list[KnowledgeBaseAttachment] = Field(
        description="List of attachments associated with the answer",
        default_factory=list,
    )


class ZammadTicket(BaseModel):
    id: int = Field(
        description="Unique identifier for the ticket",
    )
    articles: list["ZammadArticle"] = Field(
        description="List of articles associated with the ticket",
        default_factory=list,
    )


class ArticleAttachment(BaseModel):
    id: int = Field(
        description="ID of the attachment",
    )
    filename: str = Field(
        description="Filename of the attachment",
    )

    @field_validator("id", mode="before")
    @classmethod
    def cast_id_to_str(cls, value: int | str) -> str:
        """Cast id to string if it is an integer."""
        return str(value) if isinstance(value, int) else value


class ZammadArticle(BaseModel):
    id: int = Field(
        description="ID of the article",
    )
    ticket_id: int = Field(
        description="ID of the associated ticket",
    )
    text: str = Field(
        description="Body of the article",
        validation_alias=AliasChoices("text", "body"),
    )
    attachments: list["ArticleAttachment"] = Field(
        description="List of attachments for the article",
        default_factory=list,
    )
    internal: bool = Field(
        description="Whether the article is internal",
        default=False,
    )
    author: str = Field(
        description="Author of the article",
        default="-",
    )
    subject: str | None = Field(
        description="Subject of the article",
        default=None,
    )

    @field_validator("text", mode="after")
    @classmethod
    def strip_html(cls, text: str) -> str:
        """
        Normalize article text by removing HTML tags, unescaping HTML entities, and collapsing whitespace.

        Parameters:
            text: Input string that may contain HTML.

        Returns:
            The input string with HTML tags removed, HTML entities unescaped, and runs of whitespace collapsed to single spaces and trimmed.
        """
        # Remove HTML tags
        clean_text: str = re.sub(
            pattern=r"<[^>]+>",
            repl="",
            string=text,
        )
        # Unescape HTML entities
        clean_text = html.unescape(clean_text)
        # Normalize whitespace
        clean_text = re.sub(
            pattern=r"\s+",
            repl=" ",
            string=clean_text,
        ).strip()
        return clean_text


class ZammadAnswer(BaseModel):
    ticket_id: int = Field(
        description="ID of the associated ticket",
    )
    body: str = Field(
        description="Content of the article to post",
    )
    internal: bool = Field(
        description="Whether the article should be marked as internal",
        default=False,
    )
    subject: str | None = Field(default=None, description="Optional subject line for the answer")
    content_type: str = "text/html"


class ZammadTagAdd(BaseModel):
    item: str = Field(description="The tag name")
    object: str = Field(default="Ticket", description="The object type, usually 'Ticket'")
    o_id: int = Field(description="The ID of the object (e.g., ticket ID)")


# TODO: Research good defaults for model values
class ZammadSharedDraftArticle(BaseModel):
    body: str = Field(description="The body of the shared draft")
    cc: str = ""
    content_type: str = "text/html"
    sender: str = Field(default="KI Agent", alias="from")
    in_reply_to: str = ""
    internal: bool = True
    sender_id: int = 1
    subject: str = ""
    subtype: str = ""
    ticket_id: int = Field(description="The ID of the ticket")
    to: str = ""
    type: str = "note"
    type_id: int = 10

    model_config = {"populate_by_name": True}


# TODO: Research good defaults for model values
class ZammadSharedDraftAPI(BaseModel):
    form_id: str = "367646073"
    new_article: ZammadSharedDraftArticle
    ticket_attributes: dict[str, str] = Field(
        default_factory=lambda: {
            "group_id": "2",
            "owner_id": "4",
            "priority_id": "2",
            "state_id": "2",
        }
    )


class ZammadSharedDraftEAI(BaseModel):
    body: str = Field(description="The body of the shared draft")
