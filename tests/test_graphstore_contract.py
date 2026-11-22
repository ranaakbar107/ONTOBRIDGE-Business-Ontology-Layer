"""KAN-11: the GraphStore contract. Every backend must pass these tests.

To test a new backend (e.g. Neo4j), add its factory to BACKENDS.
"""

from __future__ import annotations

import inspect
import typing

import pytest

from ontobridge.core.errors import NodeNotFoundError
from ontobridge.graph import GraphStore, InMemoryGraphStore

BACKENDS = {"memory": InMemoryGraphStore}


@pytest.fixture(params=sorted(BACKENDS))
def store(request) -> GraphStore:
    s = BACKENDS[request.param]()
    s.add_node("C:1", "Customer", {"name": "Ali", "city": "Lahore"})
    s.add_node("C:2", "Customer", {"name": "Sara", "city": "Karachi"})
    s.add_node("O:1", "Order", {"amount": 100.0, "status": "paid"})
    s.add_node("O:2", "Order", {"amount": 40.0, "status": "pending"})
    s.add_node("P:1", "Product", {"name": "Mouse"})
    s.add_node("X:1", "Island", {})
    s.add_edge("C:1", "O:1", "places")
    s.add_edge("C:1", "O:2", "places")
    s.add_edge("O:1", "P:1", "contains")
    return s


def test_interface_defines_required_methods():
    for name in ("add_node", "add_edge", "get_node", "neighbors", "find_path", "query"):
        assert name in GraphStore.__abstractmethods__


def test_all_methods_have_type_hints():
    for name in GraphStore.__abstractmethods__:
        method = getattr(GraphStore, name)
        hints = typing.get_type_hints(method)
        params = [p for p in inspect.signature(method).parameters if p != "self"]
        assert "return" in hints, f"{name} has no return type"
        for p in params:
            assert p in hints, f"{name}({p}) has no type hint"


def test_get_node(store):
    node = store.get_node("C:1")
    assert (node.id, node.label, node.properties["name"]) == ("C:1", "Customer", "Ali")
    assert store.has_node("C:1") and not store.has_node("nope")
    with pytest.raises(NodeNotFoundError):
        store.get_node("nope")


def test_add_node_replaces_existing(store):
    store.add_node("C:1", "Customer", {"name": "Ali Khan"})
    assert store.get_node("C:1").properties == {"name": "Ali Khan"}
    assert store.node_count() == 6


def test_add_edge_needs_existing_nodes(store):
    with pytest.raises(NodeNotFoundError):
        store.add_edge("C:1", "missing", "places")


def test_duplicate_edge_is_kept_once(store):
    store.add_edge("C:1", "O:1", "places")
    assert store.edge_count() == 3


def test_neighbors_by_direction_and_label(store):
    out = store.neighbors("C:1", direction="out")
    assert [n.node.id for n in out] == ["O:1", "O:2"]
    assert all(n.direction == "out" and n.edge.label == "places" for n in out)
    incoming = store.neighbors("O:1", direction="in")
    assert [n.node.id for n in incoming] == ["C:1"]
    both = store.neighbors("O:1")
    assert {n.node.id for n in both} == {"C:1", "P:1"}
    assert [n.node.id for n in store.neighbors("O:1", label="contains")] == ["P:1"]
    assert len(store.neighbors("C:1", limit=1)) == 1


def test_find_path_ignores_direction(store):
    assert store.find_path("C:1", "P:1") == ["C:1", "O:1", "P:1"]
    assert store.find_path("P:1", "C:1") == ["P:1", "O:1", "C:1"]
    assert store.find_path("C:1", "X:1") is None
    assert store.find_path("C:1", "P:1", max_depth=1) is None


def test_query_with_filters(store):
    assert [n.id for n in store.query("Order")] == ["O:1", "O:2"]
    assert [n.id for n in store.query("Order", {"status": "paid"})] == ["O:1"]
    assert [n.id for n in store.query("Order", {"amount": {"gte": 50}})] == ["O:1"]
    assert [n.id for n in store.query("Order", {"status": {"in": ["paid", "pending"]}})] == [
        "O:1",
        "O:2",
    ]
    assert [n.id for n in store.query("Customer", {"name": {"contains": "sa"}})] == ["C:2"]
    assert len(store.query("Order", limit=1)) == 1
    assert store.query("Nothing") == []


def test_iterators_and_counts(store):
    assert store.node_count() == 6 and store.edge_count() == 3
    assert {n.id for n in store.nodes("Customer")} == {"C:1", "C:2"}
    assert {e.label for e in store.edges()} == {"places", "contains"}
    assert len(list(store.edges("contains"))) == 1
    store.clear()
    assert store.node_count() == 0 and store.edge_count() == 0
