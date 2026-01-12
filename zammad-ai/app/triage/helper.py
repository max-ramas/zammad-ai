import html
import operator as op
import re

from app.core.triage_settings import Action, Category, ConditionOperator


def strip_html(text: str) -> str:
    """Remove HTML tags and unescape HTML entities from text.

    Args:
        text: Raw HTML string.

    Returns:
        Plain text without tags and with entities unescaped.
    """
    # Remove HTML tags
    clean_text = re.sub(r"<[^>]+>", "", text)
    # Unescape HTML entities and normalize whitespace
    clean_text = html.unescape(clean_text)
    clean_text = " ".join(clean_text.split())
    return clean_text


def id_to_category(category_id: int, categories: list[Category], no_category_id: int) -> Category:
    for category in categories:
        if category.id == category_id:
            return category
    no_category = next((c for c in categories if c.id == no_category_id), None)
    return no_category if no_category else Category(id=-1, name="no_category")


def id_to_action(action_id: int, actions: list[Action], no_action_id: int) -> Action:
    for action in actions:
        if action.id == action_id:
            return action
    no_action = next((a for a in actions if a.id == no_action_id), None)
    return no_action if no_action else Action(id=-1, name="no_action", description="No action")


def get_operator_function(operator: ConditionOperator):
    """Map ConditionOperator enum to Python operator functions."""
    operator_map = {
        ConditionOperator.EQUALS: op.eq,
        ConditionOperator.NOT_EQUALS: op.ne,
        ConditionOperator.LESS: op.lt,
        ConditionOperator.LESS_EQUALS: op.le,
        ConditionOperator.GREATER: op.gt,
        ConditionOperator.GREATER_EQUALS: op.ge,
    }
    return operator_map.get(operator, op.eq)
