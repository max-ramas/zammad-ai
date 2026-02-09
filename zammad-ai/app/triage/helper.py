import operator as op

from app.core.settings.triage import ConditionOperator


def get_operator_function(operator: ConditionOperator):
    """Map ConditionOperator to Python operator functions."""
    operator_map = {
        "equals": op.eq,
        "not_equals": op.ne,
        "less": op.lt,
        "less_equals": op.le,
        "greater": op.gt,
        "greater_equals": op.ge,
    }
    return operator_map.get(operator, op.eq)
