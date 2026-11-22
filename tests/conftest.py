from __future__ import annotations

from pathlib import Path

import pytest

from ontobridge import load_ontology, load_project
from ontobridge.core.models import Ontology
from ontobridge.semantic import SemanticLayer

ROOT = Path(__file__).resolve().parents[1]
ECOMMERCE = ROOT / "examples" / "ecommerce"
FIXTURES = Path(__file__).resolve().parent / "fixtures"


@pytest.fixture(scope="session")
def ontology_path() -> Path:
    return ECOMMERCE / "ontology.yaml"


@pytest.fixture(scope="session")
def mapping_path() -> Path:
    return ECOMMERCE / "mapping.yaml"


@pytest.fixture(scope="session")
def ontology(ontology_path: Path) -> Ontology:
    return load_ontology(ontology_path)


@pytest.fixture(scope="session")
def layer(ontology_path: Path, mapping_path: Path) -> SemanticLayer:
    layer, _ = load_project(ontology_path, mapping_path)
    return layer


MINIMAL = {
    "entities": {
        "Customer": {"synonyms": ["client"], "properties": {"id": "string", "name": "string"}},
        "Order": {"properties": {"id": "string", "amount": "float", "status": "string"}},
    },
    "relationships": {
        "places": {"from": "Customer", "to": "Order", "cardinality": "one-to-many"},
    },
    "metrics": {
        "revenue": {
            "definition": {
                "entity": "Order",
                "aggregate": "sum",
                "field": "amount",
                "filter": {"status": "paid"},
            }
        }
    },
}


@pytest.fixture
def minimal_dict() -> dict:
    import copy

    return copy.deepcopy(MINIMAL)
