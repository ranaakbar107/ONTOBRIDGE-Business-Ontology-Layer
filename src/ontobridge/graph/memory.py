"""In-memory GraphStore built on NetworkX."""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import networkx as nx

from ontobridge.core.errors import NodeNotFoundError
from ontobridge.core.filters import matches
from ontobridge.graph.store import Direction, Edge, GraphStore, Neighbor, Node


class InMemoryGraphStore(GraphStore):
    """A ``networkx.MultiDiGraph`` with a label index for fast filtered queries."""

    def __init__(self) -> None:
        self._g = nx.MultiDiGraph()
        self._by_label: dict[str, set[str]] = {}

    # -- writes -----------------------------------------------------------------
    def add_node(self, node_id: str, label: str, properties: dict[str, Any] | None = None) -> None:
        if self._g.has_node(node_id):
            old = self._g.nodes[node_id]["label"]
            self._by_label.get(old, set()).discard(node_id)
        self._g.add_node(node_id, label=label, properties=dict(properties or {}))
        self._by_label.setdefault(label, set()).add(node_id)

    def add_edge(
        self, source: str, target: str, label: str, properties: dict[str, Any] | None = None
    ) -> None:
        for node_id in (source, target):
            if not self._g.has_node(node_id):
                raise NodeNotFoundError(f"cannot add edge '{label}': node '{node_id}' not found")
        # key=label keeps one edge per (source, target, label)
        self._g.add_edge(source, target, key=label, label=label, properties=dict(properties or {}))

    def clear(self) -> None:
        self._g.clear()
        self._by_label.clear()

    # -- reads ------------------------------------------------------------------
    def has_node(self, node_id: str) -> bool:
        return self._g.has_node(node_id)

    def get_node(self, node_id: str) -> Node:
        if not self._g.has_node(node_id):
            raise NodeNotFoundError(f"node '{node_id}' not found")
        data = self._g.nodes[node_id]
        return Node(id=node_id, label=data["label"], properties=dict(data["properties"]))

    def neighbors(
        self,
        node_id: str,
        label: str | None = None,
        direction: Direction = "both",
        limit: int | None = None,
    ) -> list[Neighbor]:
        if direction not in ("out", "in", "both"):
            raise ValueError("direction must be 'out', 'in' or 'both'")
        if not self._g.has_node(node_id):
            raise NodeNotFoundError(f"node '{node_id}' not found")
        result: list[Neighbor] = []
        if direction in ("out", "both"):
            for _, target, data in self._g.out_edges(node_id, data=True):
                if label is None or data["label"] == label:
                    edge = Edge(node_id, target, data["label"], dict(data["properties"]))
                    result.append(Neighbor(self.get_node(target), edge, "out"))
        if direction in ("in", "both"):
            for source, _, data in self._g.in_edges(node_id, data=True):
                if label is None or data["label"] == label:
                    edge = Edge(source, node_id, data["label"], dict(data["properties"]))
                    result.append(Neighbor(self.get_node(source), edge, "in"))
        result.sort(key=lambda n: (n.edge.label, n.node.id))
        return result[:limit] if limit is not None else result

    def find_path(self, source: str, target: str, max_depth: int | None = None) -> list[str] | None:
        for node_id in (source, target):
            if not self._g.has_node(node_id):
                raise NodeNotFoundError(f"node '{node_id}' not found")
        try:
            path = nx.shortest_path(self._g.to_undirected(as_view=True), source, target)
        except nx.NetworkXNoPath:
            return None
        if max_depth is not None and len(path) - 1 > max_depth:
            return None
        return list(path)

    def query(
        self, label: str, filters: dict[str, Any] | None = None, limit: int | None = None
    ) -> list[Node]:
        result: list[Node] = []
        for node_id in sorted(self._by_label.get(label, ())):
            props = self._g.nodes[node_id]["properties"]
            if matches(props, filters):
                result.append(Node(node_id, label, dict(props)))
                if limit is not None and len(result) >= limit:
                    break
        return result

    def nodes(self, label: str | None = None) -> Iterator[Node]:
        ids = sorted(self._by_label.get(label, ())) if label else list(self._g.nodes)
        for node_id in ids:
            yield self.get_node(node_id)

    def edges(self, label: str | None = None) -> Iterator[Edge]:
        for source, target, data in self._g.edges(data=True):
            if label is None or data["label"] == label:
                yield Edge(source, target, data["label"], dict(data["properties"]))

    def node_count(self) -> int:
        return self._g.number_of_nodes()

    def edge_count(self) -> int:
        return self._g.number_of_edges()
