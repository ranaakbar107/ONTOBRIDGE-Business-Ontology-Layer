"""KAN-16: Shortest path finder and entity filter query engine."""

from __future__ import annotations

import pytest

from ontobridge.core.errors import NodeNotFoundError, UnknownConceptError
from ontobridge.semantic import concept_path


def test_customer_to_product_path(ontology):
    path = concept_path(ontology, "Customer", "Product")
    assert path.sequence == ["Customer", "places", "Order", "contains", "Product"]
    assert path.text() == "Customer -places-> Order -contains-> Product"


def test_backward_path_and_same_concept(ontology):
    path = concept_path(ontology, "Category", "Customer")
    assert path.text() == ("Category <-belongs_to- Product <-contains- Order <-places- Customer")
    assert concept_path(ontology, "Order", "Order").sequence == ["Order"]


def test_layer_find_path_accepts_synonyms(layer):
    result = layer.find_path("buyer", "item")
    assert result["found"] and result["hops"] == 2
    assert result["path"] == ["Customer", "places", "Order", "contains", "Product"]


def test_filters_support_equals_and_comparisons(layer):
    paid = layer.query_entities("Order", {"status": "paid"}, limit=100)
    assert paid["count"] == 20
    assert all(r["properties"]["status"] == "paid" for r in paid["results"])
    big = layer.query_entities("Order", {"status": "paid", "amount": {"gte": 150}}, limit=100)
    assert big["count"] > 0
    assert all(r["properties"]["amount"] >= 150 for r in big["results"])
    # string numbers are coerced to the property type
    assert layer.query_entities("Order", {"amount": {"gte": "150"}})["count"] >= big["count"]


def test_results_accept_a_limit(layer):
    result = layer.query_entities("Order", limit=5)
    assert result["returned"] == 5 and result["count"] == 30 and result["truncated"]
    capped = layer.query_entities("Order", limit=10_000)
    assert capped["returned"] == 30  # cap is 100, there are only 30


def test_dates_are_json_strings(layer):
    row = layer.query_entities("Order", {"id": "O001"})["results"][0]
    assert row["properties"]["order_date"] == "2026-01-03"
    after = layer.query_entities("Order", {"order_date": {"gte": "2026-10-01"}}, limit=100)
    assert all(r["properties"]["order_date"] >= "2026-10-01" for r in after["results"])


def test_unknown_property_and_concept_errors(layer):
    with pytest.raises(ValueError, match="Order has no property 'colour'"):
        layer.query_entities("Order", {"colour": "red"})
    with pytest.raises(UnknownConceptError, match="Did you mean: Order"):
        layer.query_entities("Ordr")


def test_neighbors(layer):
    result = layer.get_neighbors("Customer:C001", "places", "out")
    assert result["node"]["properties"]["name"] == "Ali Khan"
    assert {n["concept"] for n in result["neighbors"]} == {"Order"}
    assert result["count"] == 4
    assert layer.get_neighbors("Customer:C001", "ordered")["count"] == 4  # synonym
    with pytest.raises(NodeNotFoundError, match="Customer:C001"):
        layer.get_neighbors("C001")
