"""KAN-12: In-memory NetworkX GraphStore implementation."""

from __future__ import annotations

import datetime as dt
import time

from ontobridge.graph import GraphStore, InMemoryGraphStore


def test_is_a_graph_store():
    assert isinstance(InMemoryGraphStore(), GraphStore)


def test_typed_properties_are_kept():
    s = InMemoryGraphStore()
    s.add_node("O:1", "Order", {"amount": 9.5, "paid": True, "day": dt.date(2026, 1, 1)})
    s.add_node("O:2", "Order", {"amount": 1.0})
    s.add_edge("O:1", "O:2", "related", {"weight": 2})
    props = s.get_node("O:1").properties
    assert props == {"amount": 9.5, "paid": True, "day": dt.date(2026, 1, 1)}
    assert next(s.edges()).properties == {"weight": 2}
    # returned dicts are copies: callers cannot mutate the store by accident
    props["amount"] = 0
    assert s.get_node("O:1").properties["amount"] == 9.5


def test_relabel_updates_label_index():
    s = InMemoryGraphStore()
    s.add_node("n", "A")
    s.add_node("n", "B")
    assert s.query("A") == [] and [n.id for n in s.query("B")] == ["n"]


def test_10000_nodes_load_quickly():
    s = InMemoryGraphStore()
    start = time.perf_counter()
    for i in range(10_000):
        s.add_node(f"N:{i}", "Thing", {"i": i})
    for i in range(1, 10_000):
        s.add_edge(f"N:{i - 1}", f"N:{i}", "next")
    elapsed = time.perf_counter() - start
    assert s.node_count() == 10_000 and s.edge_count() == 9_999
    assert elapsed < 5, f"took {elapsed:.2f}s"
    assert len(s.query("Thing", {"i": {"gte": 9_990}})) == 10
