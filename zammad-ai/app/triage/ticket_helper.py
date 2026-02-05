import httpx
from truststore import inject_into_ssl

from app.core.core_settings import ZammadSettings
from app.models.triage import Attachment, ZammadArticleModel, ZammadTicketModel
from app.utils.logging import getLogger

from .helper import strip_html

inject_into_ssl()

HTTP_TIMEOUT_SECONDS = 30

logger = getLogger("zammad-ai.triage.ticket_helper")


async def get_data_from_zammad(id: str, settings: ZammadSettings) -> ZammadTicketModel:
    articles = await get_articles_by_id(id, settings=settings)
    ticket = ZammadTicketModel(
        id=id,
        articles=articles if articles else [],
    )
    return ticket


async def get_articles_by_id(ticket_id: str, settings: ZammadSettings) -> list[ZammadArticleModel] | None:
    url = f"{settings.base_url}/api/v1/ticket_articles/by_ticket/{ticket_id}"
    headers = {
        "Authorization": f"Bearer {settings.auth_token}",
    }
    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            json = response.json()
            articles: list[ZammadArticleModel] = []
            for item in json:
                attachments: list[Attachment] = []
                for attachment in item["attachments"]:
                    attach = Attachment(
                        id=str(attachment["id"]),
                        filename=str(attachment["filename"]),
                        size=str(attachment["size"]),
                        preferences=attachment.get("preferences", {}),
                    )
                    attachments.append(attach)
                article = ZammadArticleModel(
                    id=str(item["id"]),
                    ticket_id=str(item["ticket_id"]),
                    text=strip_html(str(item["body"])),
                    attachments=attachments,
                    internal=item.get("internal", False),
                    author=item.get("from", "-"),
                )

                articles.append(article)
            return articles
    except Exception as e:
        logger.exception("Error fetching articles for ticket %s: %s", ticket_id, e)


async def create_zammad_article(ticket_id: str, text: str, internal: bool, settings: ZammadSettings) -> bool:
    url = f"{settings.base_url}/api/v1/ticket_articles"
    headers = {
        "Authorization": f"Bearer {settings.auth_token}",
    }
    # TODO check payload data fields (ids, types, etc.)
    payload = {
        "ticket_id": ticket_id,
        "subject": "Call note",
        "body": text,
        "content_type": "text/html",
        "sender": "KI Agent",
        "type": "phone",
        "internal": internal,
        "time_unit": "15",
    }

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(url, headers=headers, json=payload)
            if response.status_code == 422:
                logger.warning("Ticket created but with issues %s: %s", ticket_id, response.text)
                return True
            response.raise_for_status()
            return True
    except Exception as e:
        logger.exception("Error creating article for ticket %s: %s", ticket_id, e)
        return False


async def create_zammad_shared_draft(ticket_id: str, text: str, settings: ZammadSettings) -> bool:
    url = f"{settings.base_url}/api/v1/tickets/{ticket_id}/shared_draft"
    headers = {
        "Authorization": f"Bearer {settings.auth_token}",
    }
    # TODO check payload data fields (ids, types, etc.)
    payload = {
        "form_id": "367646073",
        "new_article": {
            "body": text,
            "cc": "",
            "content_type": "text/html",
            "from": "KI Agent",
            "in_reply_to": "",
            "internal": True,
            "sender_id": 1,
            "subject": "",
            "subtype": "",
            "ticket_id": ticket_id,
            "to": "",
            "type": "note",
            "type_id": 10,
        },
        "ticket_attributes": {"group_id": "2", "owner_id": "4", "priority_id": "2", "state_id": "2"},
    }

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.put(url, headers=headers, json=payload)
            response.raise_for_status()
            return True
    except Exception as e:
        logger.exception("Error creating shared draft for ticket %s: %s", ticket_id, e)
        return False


async def set_ticket_tag(ticket_id: str, tag: str, settings: ZammadSettings) -> bool:
    url = f"{settings.base_url}/api/v1/tags/add"
    headers = {
        "Authorization": f"Bearer {settings.auth_token}",
    }
    payload = {"item": tag, "object": "Ticket", "o_id": ticket_id}

    try:
        async with httpx.AsyncClient(timeout=HTTP_TIMEOUT_SECONDS) as client:
            response = await client.post(url, headers=headers, json=payload)
            response.raise_for_status()
            return True
    except Exception as e:
        logger.exception("Error setting tags for ticket %s: %s", ticket_id, e)
        return False
