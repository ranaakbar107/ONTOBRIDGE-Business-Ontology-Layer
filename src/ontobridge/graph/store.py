"""The GraphStore interface.

The builder and the semantic layer only talk to this interface, so the backend
can change (NetworkX today; Neo4j, Kuzu or Omnigraph later) without touching them.
A new backend passes the shared contract suite in ``tests/test_graphstore_contract.py``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Literal

Direction = Literal["out", "in", "both"]


@dataclass(frozen=True)
class Node:
    id: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    label: str
    properties: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class Neighbor:
    """A node connected to another node, with the edge and its direction."""

    node: Node
    edge: Edge
    direction: Literal["out", "in"]


class GraphStore(ABC):
    """Abstract labelled property graph."""

    @abstractmethod
    def add_node(self, node_id: str, label: str, properties: dict[str, Any] | None = None) -> None:
        """Insert a node, or replace the label and properties of an existing one."""

    @abstractmethod
    def add_edge(
        self, source: str, target: str, label: str, properties: dict[str, Any] | None = None
    ) -> None:
        """Insert a directed edge. Both nodes must exist (NodeNotFoundError otherwise).
        Adding the same (source, target, label) twice keeps one edge."""

    @abstractmethod
    def has_node(self, node_id: str) -> bool: ...

    @abstractmethod
    def get_node(self, node_id: str) -> Node:
        """Return a node or raise NodeNotFoundError."""

    @abstractmethod
    def neighbors(
        self,
        node_id: str,
        label: str | None = None,
        direction: Direction = "both",
        limit: int | None = None,
    ) -> list[Neighbor]:
        """Nodes connected to ``node_id``, optionally only through edges named ``label``."""

    @abstractmethod
    def find_path(self, source: str, target: str, max_depth: int | None = None) -> list[str] | None:
        """Shortest path of node ids, ignoring edge direction. ``None`` if no path."""

    @abstractmethod
    def query(
        self, label: str, filters: dict[str, Any] | None = None, limit: int | None = None
    ) -> list[Node]:
        """Nodes with ``label`` whose properties match ``filters``
        (see :mod:`ontobridge.core.filters`)."""

    @abstractmethod
    def nodes(self, label: str | None = None) -> Iterator[Node]: ...

    @abstractmethod
    def edges(self, label: str | None = None) -> Iterator[Edge]: ...

    @abstractmethod
    def node_count(self) -> int: ...

    @abstractmethod
    def edge_count(self) -> int: ...

    @abstractmethod
    def clear(self) -> None: ...
