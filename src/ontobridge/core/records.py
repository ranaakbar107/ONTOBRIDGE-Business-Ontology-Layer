"""Internal data model produced by the input adapters and consumed by the graph builder."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class RawRow:
    """One row exactly as read from a file, with its position for error messages."""

    row_number: int
    values: dict[str, Any]


@dataclass
class RawTable:
    """Rows read by a data adapter (CSV, JSON...) before they are mapped to the ontology."""

    source: str
    rows: list[RawRow] = field(default_factory=list)


@dataclass(frozen=True)
class Record:
    """A typed instance of an entity, e.g. one Customer."""

    entity: str
    key: Any
    properties: dict[str, Any]
    source: str = ""
    row_number: int | None = None

    @property
    def node_id(self) -> str:
        return node_id(self.entity, self.key)


@dataclass(frozen=True)
class Link:
    """An instance of a relationship between two records."""

    relationship: str
    from_entity: str
    from_key: Any
    to_entity: str
    to_key: Any
    source: str = ""
    row_number: int | None = None

    @property
    def from_id(self) -> str:
        return node_id(self.from_entity, self.from_key)

    @property
    def to_id(self) -> str:
        return node_id(self.to_entity, self.to_key)


@dataclass
class Dataset:
    """All records and links for one ontology."""

    records: dict[str, list[Record]] = field(default_factory=dict)
    links: dict[str, list[Link]] = field(default_factory=dict)

    def add_records(self, entity: str, records: list[Record]) -> None:
        self.records.setdefault(entity, []).extend(records)

    def add_links(self, relationship: str, links: list[Link]) -> None:
        self.links.setdefault(relationship, []).extend(links)


def node_id(entity: str, key: Any) -> str:
    """Stable graph node id for an entity instance, e.g. ``Customer:C001``."""
    return f"{entity}:{key}"
