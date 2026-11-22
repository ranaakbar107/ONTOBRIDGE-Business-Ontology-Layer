"""Small filter language shared by metrics and entity queries.

A filter is a mapping of property name to either a plain value (equality)
or an operator mapping, for example::

    {"status": "paid"}
    {"amount": {"gte": 100}, "status": {"in": ["paid", "shipped"]}}
"""

from __future__ import annotations

from typing import Any

OPERATORS = {"eq", "ne", "gt", "gte", "lt", "lte", "in", "contains"}


def _compare(op: str, actual: Any, expected: Any) -> bool:
    if op == "eq":
        return actual == expected
    if op == "ne":
        return actual != expected
    if op == "in":
        return actual in expected
    if op == "contains":
        return actual is not None and str(expected).lower() in str(actual).lower()
    if actual is None:
        return False
    try:
        if op == "gt":
            return actual > expected
        if op == "gte":
            return actual >= expected
        if op == "lt":
            return actual < expected
        if op == "lte":
            return actual <= expected
    except TypeError:
        # Comparing e.g. a date with a string: compare their text forms.
        return _compare(op, str(actual), str(expected))
    raise ValueError(f"Unknown filter operator '{op}'. Use one of {sorted(OPERATORS)}")


def matches(properties: dict[str, Any], filters: dict[str, Any] | None) -> bool:
    """Return True when ``properties`` satisfy every condition in ``filters``."""
    if not filters:
        return True
    for field, condition in filters.items():
        actual = properties.get(field)
        if isinstance(condition, dict):
            for op, expected in condition.items():
                if not _compare(op, actual, expected):
                    return False
        elif not _compare("eq", actual, condition):
            return False
    return True


def validate_filter(filters: dict[str, Any] | None) -> list[str]:
    """Return problems with a filter's operators (field names are checked elsewhere)."""
    problems: list[str] = []
    for field, condition in (filters or {}).items():
        if isinstance(condition, dict):
            for op in condition:
                if op not in OPERATORS:
                    problems.append(
                        f"filter on '{field}' uses unknown operator '{op}' "
                        f"(allowed: {', '.join(sorted(OPERATORS))})"
                    )
    return problems
