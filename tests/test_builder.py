"""KAN-21: Graph builder turns ontology and data into typed nodes and edges."""

from __future__ import annotations

import pytest

from ontobridge.adapters import load_dataset
from ontobridge.builder import GraphBuilder
from ontobridge.core.errors import GraphBuildError
from ontobridge.core.models import Ontology
from ontobridge.core.records import Dataset, Link, Record
from ontobridge.graph import InMemoryGraphStore


def _rec(entity, key, **props):
    return Record(entity=entity, key=key, properties={"id": key, **props})


def test_ecommerce_builds_customer_order_product_graph(ontology, mapping_path):
    store = InMemoryGraphStore()
    report = GraphBuilder(ontology, store).build(load_dataset(ontology, mapping_path))
    assert report.nodes_by_entity == {"Customer": 10, "Order": 30, "Product": 15, "Category": 4}
    assert report.edges_by_relationship["places"] == 30
    assert report.edges == store.edge_count() and report.nodes == store.node_count()
    labels = {e.label for e in store.edges()}
    assert {"places", "contains"} <= labels
    places = store.neighbors("Customer:C001", "places", "out")
    assert all(n.node.label == "Order" for n in places)
    contains = store.neighbors("Order:O001", "contains", "out")
    assert contains and all(n.node.label == "Product" for n in contains)


def test_every_node_conforms_to_ontology(ontology, mapping_path):
    store = InMemoryGraphStore()
    GraphBuilder(ontology, store).build(load_dataset(ontology, mapping_path))
    for node in store.nodes():
        assert set(node.properties) == set(ontology.entities[node.label].properties)


@pytest.fixture
def onto(minimal_dict) -> Ontology:
    return Ontology.model_validate(minimal_dict)


def test_records_that_break_the_ontology_are_rejected_with_report(onto):
    ds = Dataset()
    ds.add_records("Customer", [_rec("Customer", "C1", name="Ali", age=3)])  # unknown prop
    ds.add_records("Order", [_rec("Order", "O1", amount="ten", status="paid")])  # bad type
    ds.add_records("Ghost", [_rec("Ghost", "G1")])  # unknown entity
    store = InMemoryGraphStore()
    with pytest.raises(GraphBuildError) as info:
        GraphBuilder(onto, store).build(ds)
    text = str(info.value)
    assert "unknown property 'age'" in text
    assert "'amount' should be float" in text
    assert "unknown entity 'Ghost'" in text
    assert store.node_count() == 0  # nothing written


def test_missing_required_property(onto):
    ds = Dataset()
    ds.add_records("Order", [Record("Order", "O1", {"id": "O1", "amount": 1.0})])
    with pytest.raises(GraphBuildError, match="missing required property 'status'"):
        GraphBuilder(onto, InMemoryGraphStore()).build(ds)


def test_cardinality_is_enforced(onto):
    ds = Dataset()
    ds.add_records("Customer", [_rec("Customer", "C1", name="A"), _rec("Customer", "C2", name="B")])
    ds.add_records("Order", [_rec("Order", "O1", amount=1.0, status="paid")])
    ds.add_links(
        "places",
        [
            Link("places", "Customer", "C1", "Order", "O1"),
            Link("places", "Customer", "C2", "Order", "O1"),  # one-to-many: O1 has 2 customers
        ],
    )
    with pytest.raises(GraphBuildError, match="cardinality one-to-many of 'places' broken"):
        GraphBuilder(onto, InMemoryGraphStore()).build(ds)


def test_links_to_missing_records_and_wrong_types(onto):
    ds = Dataset()
    ds.add_records("Customer", [_rec("Customer", "C1", name="A")])
    ds.add_links(
        "places",
        [
            Link("places", "Customer", "C1", "Order", "O404"),
            Link("places", "Order", "C1", "Customer", "C1"),
        ],
    )
    ds.add_links("ships", [Link("ships", "Customer", "C1", "Customer", "C1")])
    with pytest.raises(GraphBuildError) as info:
        GraphBuilder(onto, InMemoryGraphStore()).build(ds)
    text = str(info.value)
    assert "missing record(s): Order:O404" in text
    assert "must link Customer -> Order" in text
    assert "unknown relationship 'ships'" in text


def test_empty_dataset_builds_empty_graph(onto):
    report = GraphBuilder(onto, InMemoryGraphStore()).build(Dataset())
    assert report.nodes == 0 and report.edges == 0
