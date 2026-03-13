import html
import re
from uuid import UUID

from pydantic import AliasChoices, BaseModel, Field, field_validator


class KnowledgeBaseAnswer(BaseModel):
    id: UUID = Field(
        description="The ID of the answer",
    )
    title: str = Field(
        description="The title of the answer",
    )
    content: str = Field(
        description="The content of the answer",
    )
    attachments: dict[str, str] = Field(
        description="Dict of attachments associated with the filename",
        default_factory=dict,
    )

    @field_validator("content", mode="after")
    @classmethod
    def strip_html(cls, text: str) -> str:
        """
        Normalize text by removing HTML tags, unescaping HTML entities, and collapsing whitespace.

        Parameters:
            text (str): Input string that may contain HTML.

        Returns:
            str: The input string with HTML tags removed, HTML entities unescaped, and consecutive whitespace collapsed to single spaces and trimmed.
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


class ZammadTicket(BaseModel):
    id: str = Field(
        description="Unique identifier for the ticket",
    )
    articles: list["ZammadArticle"] = Field(
        description="List of articles associated with the ticket",
        default_factory=list,
    )


class ZammadArticle(BaseModel):
    id: str = Field(
        description="ID of the article",
    )
    ticket_id: str = Field(
        description="ID of the associated ticket",
    )
    text: str = Field(
        description="Body of the article",
        validation_alias=AliasChoices("text", "body"),
    )
    attachments: list["Attachment"] = Field(
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


class Attachment(BaseModel):
    id: str = Field(
        description="ID of the attachment",
    )
    filename: str = Field(
        description="Filename of the attachment",
    )
    size: str = Field(
        description="Size of the attachment",
    )
    preferences: dict = Field(
        description="Preferences of the attachment",
        default_factory=dict,
    )


class ZammadAnswer(BaseModel):
    ticket_id: str = Field(
        description="ID of the associated ticket",
    )
    body: str = Field(
        description="Content of the article to post",
    )
    internal: bool = Field(
        description="Whether the article should be marked as internal",
        default=False,
    )
    subject: str = "Call note"
    content_type: str = "text/html"
    sender: str = "KI Agent"
    type: str = "phone"
    time_unit: str = "15"


class ZammadTagAdd(BaseModel):
    item: str = Field(description="The tag name")
    object: str = Field(default="Ticket", description="The object type, usually 'Ticket'")
    o_id: str = Field(description="The ID of the object (e.g., ticket ID)")


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
    ticket_id: str = Field(description="The ID of the ticket")
    to: str = ""
    type: str = "note"
    type_id: int = 10

    model_config = {"populate_by_name": True}


# TODO: Research good defaults for model values
class ZammadSharedDraft(BaseModel):
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
