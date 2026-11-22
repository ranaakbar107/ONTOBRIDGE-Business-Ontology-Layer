"""ontobridge: a business ontology layer for AI agents.

Define your business in YAML, build an in-memory knowledge graph and let
agents query its meaning over MCP.
"""

__version__ = "0.1.0"

from ontobridge.adapters import load_dataset, load_ontology  # noqa: E402
from ontobridge.core import Ontology, OntologyValidationError  # noqa: E402
from ontobridge.graph import GraphStore, InMemoryGraphStore  # noqa: E402
from ontobridge.project import load_project  # noqa: E402
from ontobridge.semantic import SemanticLayer  # noqa: E402

__all__ = [
    "GraphStore",
    "InMemoryGraphStore",
    "Ontology",
    "OntologyValidationError",
    "SemanticLayer",
    "__version__",
    "load_dataset",
    "load_ontology",
    "load_project",
]
