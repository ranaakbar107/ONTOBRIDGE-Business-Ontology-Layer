"""Shortest path between two concepts in the ontology schema."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import networkx as nx

from ontobridge.core.models import Ontology


@dataclass(frozen=True)
class PathStep:
    from_concept: str
    relationship: str
    to_concept: str
    direction: str  # "forward" if the relationship points from_concept -> to_concept

    def to_dict(self) -> dict[str, str]:
        return {
            "from": self.from_concept,
            "relationship": self.relationship,
            "to": self.to_concept,
            "direction": self.direction,
        }


@dataclass(frozen=True)
class ConceptPath:
    concepts: list[str]
    steps: list[PathStep] = field(default_factory=list)

    @property
    def sequence(self) -> list[str]:
        """Concepts and relationships interleaved: Customer, places, Order, contains, Product."""
        if not self.steps:
            return list(self.concepts)
        seq = [self.steps[0].from_concept]
        for step in self.steps:
            seq += [step.relationship, step.to_concept]
        return seq

    def text(self) -> str:
        if not self.steps:
            return self.concepts[0] if self.concepts else ""
        parts = [self.steps[0].from_concept]
        for step in self.steps:
            arrow = (
                f" -{step.relationship}-> "
                if step.direction == "forward"
                else (f" <-{step.relationship}- ")
            )
            parts.append(arrow + step.to_concept)
        return "".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": self.sequence,
            "hops": len(self.steps),
            "text": self.text(),
            "steps": [s.to_dict() for s in self.steps],
        }


def schema_graph(ontology: Ontology) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    g.add_nodes_from(ontology.entities)
    for rel in ontology.relationships.values():
        g.add_edge(rel.from_entity, rel.to_entity, key=rel.name)
    return g


def concept_path(ontology: Ontology, source: str, target: str) -> ConceptPath | None:
    """Shortest path between two entities, ignoring relationship direction."""
    g = schema_graph(ontology)
    try:
        nodes = nx.shortest_path(g.to_undirected(as_view=True), source, target)
    except nx.NetworkXNoPath:
        return None
    steps: list[PathStep] = []
    for a, b in zip(nodes, nodes[1:], strict=False):
        forward = sorted(g.get_edge_data(a, b, default={}))
        if forward:
            steps.append(PathStep(a, forward[0], b, "forward"))
        else:
            backward = sorted(g.get_edge_data(b, a, default={}))
            steps.append(PathStep(a, backward[0], b, "backward"))
    return ConceptPath(concepts=list(nodes), steps=steps)
