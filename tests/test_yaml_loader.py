"""KAN-10: YAML ontology loader and fail-fast schema validator."""

from __future__ import annotations

import pytest

from ontobridge.adapters import load_ontology, ontology_from_yaml_string
from ontobridge.core.errors import OntologyValidationError

from .conftest import FIXTURES


def test_ecommerce_example_loads_without_errors(ontology_path):
    onto = load_ontology(ontology_path)
    assert set(onto.entities) == {"Customer", "Order", "Product", "Category"}
    assert set(onto.relationships) == {"places", "contains", "belongs_to"}
    assert "revenue" in onto.metrics
    assert "buyer" in onto.entities["Customer"].synonyms


INVALID = [
    ("unknown_entity.yaml", "unknown entity 'Ordr'"),
    ("bad_cardinality.yaml", "relationships.places.cardinality"),
    ("missing_property.yaml", "missing property 'amount'"),
    ("missing_key.yaml", "key 'customer_id'"),
    ("unknown_field.yaml", "propertes: unknown field"),
    ("bad_property_type.yaml", "amount.type"),
    ("not_a_mapping.yaml", "top level must be a mapping"),
    ("broken_syntax.yaml", "Invalid YAML"),
    ("duplicate_synonym.yaml", "term 'client' is used by both"),
    ("metric_unknown_entity.yaml", "unknown entity 'Sale'"),
]


def test_there_are_at_least_five_invalid_fixtures():
    assert len(list(FIXTURES.glob("invalid/*.yaml"))) >= 5


@pytest.mark.parametrize(("file_name", "message"), INVALID)
def test_invalid_yaml_fails_fast_and_names_the_problem(file_name, message):
    with pytest.raises(OntologyValidationError) as info:
        load_ontology(FIXTURES / "invalid" / file_name)
    assert message in str(info.value)
    assert file_name in str(info.value)  # error says which file


def test_missing_file_has_clear_error(tmp_path):
    with pytest.raises(OntologyValidationError, match="not found"):
        load_ontology(tmp_path / "nope.yaml")


def test_error_lists_every_problem():
    text = """
entities:
  Customer:
    properties: {id: string}
relationships:
  a: {from: Customer, to: X, cardinality: one-to-many}
  b: {from: Y, to: Customer, cardinality: one-to-many}
"""
    with pytest.raises(OntologyValidationError) as info:
        ontology_from_yaml_string(text)
    assert len(info.value.errors) == 2
    assert "'X'" in str(info.value) and "'Y'" in str(info.value)
