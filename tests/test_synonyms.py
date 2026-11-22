"""KAN-14: Synonym indexer and business term resolver."""

from __future__ import annotations

import pytest

from ontobridge.semantic import TermResolver, normalize, singular


@pytest.fixture
def resolver(ontology):
    return TermResolver(ontology)


@pytest.mark.parametrize("term", ["buyer", "client", "Customer", "BUYER", "  clients ", "Buyers"])
def test_synonyms_resolve_to_customer(resolver, term):
    assert resolver.resolve_entity(term) == "Customer"


def test_resolution_details(resolver):
    (m,) = resolver.resolve("buyers")
    assert m.to_dict() == {
        "term": "buyers",
        "target": "Customer",
        "kind": "entity",
        "matched_on": "buyer",
    }


@pytest.mark.parametrize(
    ("term", "target", "kind"),
    [
        ("categories", "Category", "entity"),
        ("product category", "Category", "entity"),
        ("sales", "revenue", "metric"),
        ("AOV", "average_order_value", "metric"),
        ("ordered", "places", "relationship"),
        ("items", "Product", "entity"),
    ],
)
def test_other_terms(resolver, term, target, kind):
    (m,) = resolver.resolve(term)
    assert (m.target, m.kind) == (target, kind)


def test_unknown_term_returns_empty_not_error(resolver):
    assert resolver.resolve("ad spend") == []
    assert resolver.resolve("") == []
    assert resolver.resolve_entity("unicorn") is None


@pytest.mark.parametrize(
    ("word", "expected"),
    [
        ("orders", "order"),
        ("categories", "category"),
        ("boxes", "box"),
        ("status", "status"),
        ("address", "address"),
        ("bus", "bus"),
    ],
)
def test_singular(word, expected):
    assert singular(word) == expected


def test_normalize_handles_case_snake_and_camel():
    assert normalize("OrderItems") == "order item"
    assert normalize("order_items") == "order item"
    assert normalize("Line-Item!") == "line item"
