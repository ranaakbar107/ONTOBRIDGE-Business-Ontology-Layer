"""One call from files on disk to a ready semantic layer (the build-time pipeline).

1. load YAML (and the data mapping)   2. validate against the schema
3. create nodes and edges             4. index synonyms and metrics
5. graph ready in memory
"""

from __future__ import annotations

from pathlib import Path

from ontobridge.adapters import load_dataset, load_ontology
from ontobridge.builder import BuildReport, GraphBuilder
from ontobridge.core.records import Dataset
from ontobridge.graph import GraphStore, InMemoryGraphStore
from ontobridge.semantic import SemanticLayer


def load_project(
    ontology_path: str | Path,
    mapping_path: str | Path | None = None,
    store: GraphStore | None = None,
) -> tuple[SemanticLayer, BuildReport]:
    """Load an ontology (and optional data), build the graph and return the semantic layer."""
    ontology = load_ontology(ontology_path)
    dataset = load_dataset(ontology, mapping_path) if mapping_path else Dataset()
    store = store or InMemoryGraphStore()
    report = GraphBuilder(ontology, store).build(dataset)
    sources = {"ontology_file": Path(ontology_path).name}
    if mapping_path:
        sources["data_mapping"] = Path(mapping_path).name
    return SemanticLayer(ontology, store, sources), report
