"""KAN-9: Pydantic v2 models for Entities, Relationships, Metrics and Synonyms."""

from __future__ import annotations

import datetime as dt

import pytest
from pydantic import ValidationError

from ontobridge.core.models import (
    Aggregate,
    Cardinality,
    Entity,
    Metric,
    Ontology,
    Property,
    PropertyType,
    Relationship,
    Synonym,
)


def test_valid_entity_with_short_and_long_property_forms():
    e = Entity(
        name="Customer",
        synonyms=["buyer"],
        properties={"id": "string", "signup": {"type": "date", "required": False}},
    )
    assert e.properties["id"].type is PropertyType.STRING
    assert e.properties["signup"].type is PropertyType.DATE
    assert e.properties["signup"].required is False


def test_entity_key_must_be_a_property():
    with pytest.raises(ValidationError, match="key 'customer_id'"):
        Entity(name="Customer", key="customer_id", properties={"id": "string"})


def test_entity_needs_properties():
    with pytest.raises(ValidationError, match="at least one property"):
        Entity(name="Empty", properties={})


def test_property_rejects_unknown_type():
    with pytest.raises(ValidationError):
        Property(name="amount", type="money")


def test_relationship_uses_from_and_to_aliases():
    r = Relationship.model_validate(
        {"name": "places", "from": "Customer", "to": "Order", "cardinality": "one-to-many"}
    )
    assert (r.from_entity, r.to_entity, r.cardinality) == (
        "Customer",
        "Order",
        Cardinality.ONE_TO_MANY,
    )


def test_relationship_rejects_bad_cardinality():
    with pytest.raises(ValidationError):
        Relationship.model_validate({"name": "x", "from": "A", "to": "B", "cardinality": "lots"})


def test_metric_formula_and_count_without_field():
    m = Metric.model_validate(
        {
            "name": "revenue",
            "definition": {
                "entity": "Order",
                "aggregate": "sum",
                "field": "amount",
                "filter": {"status": "paid"},
            },
        }
    )
    assert m.formula() == "sum of Order.amount where status = paid"
    c = Metric.model_validate(
        {"name": "orders", "definition": {"entity": "Order", "aggregate": "count"}}
    )
    assert c.definition.aggregate is Aggregate.COUNT
    assert c.formula() == "count of Order records"


def test_metric_sum_needs_field():
    with pytest.raises(ValidationError, match="needs a 'field'"):
        Metric.model_validate(
            {"name": "bad", "definition": {"entity": "Order", "aggregate": "sum"}}
        )


def test_valid_ontology_and_synonym_index(minimal_dict):
    onto = Ontology.model_validate(minimal_dict)
    assert set(onto.entities) == {"Customer", "Order"}
    syns = onto.synonym_index()
    assert Synonym(term="client", target="Customer", kind="entity") in syns
    assert any(s.kind == "metric" and s.target == "revenue" for s in syns)
    assert [r.name for r in onto.relationships_of("Order")] == ["places"]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda d: d["relationships"]["places"].update(to="Ordr"), "unknown entity 'Ordr'"),
        (
            lambda d: d["metrics"]["revenue"]["definition"].update(field="total"),
            "missing property 'total'",
        ),
        (
            lambda d: d["metrics"]["revenue"]["definition"].update(filter={"state": "paid"}),
            "filters on missing property 'state'",
        ),
        (
            lambda d: d["metrics"]["revenue"]["definition"].update(field="status"),
            "non-numeric",
        ),
        (
            lambda d: d["entities"]["Order"].update(synonyms=["client"]),
            "term 'client' is used by both",
        ),
        (lambda d: d.update(entities={}), "at least one entity"),
    ],
)
def test_invalid_ontology_raises_clear_error(minimal_dict, mutate, message):
    mutate(minimal_dict)
    with pytest.raises(ValidationError, match=message):
        Ontology.model_validate(minimal_dict)


@pytest.mark.parametrize(
    ("ptype", "raw", "expected"),
    [
        (PropertyType.INTEGER, "42", 42),
        (PropertyType.FLOAT, "19.50", 19.5),
        (PropertyType.BOOLEAN, "yes", True),
        (PropertyType.BOOLEAN, "false", False),
        (PropertyType.DATE, "2026-01-03", dt.date(2026, 1, 3)),
        (PropertyType.STRING, 7, "7"),
    ],
)
def test_property_type_coercion(ptype, raw, expected):
    assert ptype.coerce(raw) == expected


@pytest.mark.parametrize(
    ("ptype", "raw"),
    [(PropertyType.INTEGER, "abc"), (PropertyType.BOOLEAN, "maybe"), (PropertyType.DATE, "x")],
)
def test_property_type_coercion_errors(ptype, raw):
    with pytest.raises(ValueError):
        ptype.coerce(raw)
