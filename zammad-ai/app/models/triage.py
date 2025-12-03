from app.triage.settings import Action, Category
from pydantic import BaseModel, Field


class KnowledgeBaseAnswer(BaseModel):
    id: str = Field(..., description="The ID of the answer")
    title: str = Field(..., description="The title of the answer")
    content: str = Field(..., description="The content of the answer")
    attachments: dict[str, str] = Field(..., description="Dict of attachments associated with the filename")


class CategorizationResult(BaseModel):
    """
    A structured response for a categorization request.
    """

    category: Category | None = Field(description=("The predicted category for the text."))
    reasoning: str = Field(description="A single sentence explaining why the text fits the chosen category.Translate the text in german.")
    confidence: float = Field(
        description="Value from 0.0 to 1.0 on how sure / confident you are in your categorisation",
        ge=0.0,
        le=1.0,
    )


class TriageResult(BaseModel):
    """Complete result of the triage process."""

    category: Category = Field(description="The predicted category")
    action: Action = Field(description="The recommended action")
    reasoning: str = Field(description="Explanation for the categorization")
    confidence: float = Field(description="Confidence score (0.0 to 1.0)")


class Attachment(BaseModel):
    id: str = Field(..., description="ID of the attachment")
    filename: str = Field(..., description="Filename of the attachment")
    size: str = Field(..., description="Size of the attachment")
    preferences: dict = Field(..., description="Preferences of the attachment")


class ZammadArticleModel(BaseModel):
    id: str = Field(..., description="ID of the article")
    ticket_id: str = Field(..., description="ID of the associated ticket")
    text: str = Field(..., description="Body of the article")
    attachments: list[Attachment] = Field(..., description="List of attachments for the article")
    internal: bool = Field(..., description="Whether the article is internal")
    author: str = Field(..., description="Author of the article")


class ZammadTicketModel(BaseModel):
    id: str = Field(..., description="Unique identifier for the ticket")
    articles: list[ZammadArticleModel] = Field(..., description="List of articles associated with the ticket")


class DaysSinceRequestResponse(BaseModel):
    days_since_request: int = Field(description="Number of days since the request was made")
    reason: str = Field(description="Reason for the calculation")


class ProcessingIdResponse(BaseModel):
    processing_id: str = Field(description="Extracted processing ID from the text")
    reason: str = Field(description="Reason for the extraction")
