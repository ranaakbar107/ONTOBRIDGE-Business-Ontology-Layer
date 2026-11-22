"""The semantic layer: one object that answers every question an agent can ask.

Each method returns plain JSON-ready dicts and includes a ``source`` block so an
agent can say where an answer came from. The MCP server is a thin wrapper over
these methods, so everything here works (and is tested) without MCP.
"""

from __future__ import annotations

import datetime as dt
import difflib
from typing import Any

from ontobridge.core.errors import NodeNotFoundError, UnknownConceptError
from ontobridge.core.models import Ontology
from ontobridge.graph.store import GraphStore
from ontobridge.semantic.answerable import AnswerabilityChecker
from ontobridge.semantic.metrics import MetricEngine
from ontobridge.semantic.paths import concept_path
from ontobridge.semantic.synonyms import TermResolver

DEFAULT_LIMIT = 20
MAX_LIMIT = 100


def to_jsonable(value: Any) -> Any:
    if isinstance(value, dt.date | dt.datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: to_jsonable(v) for k, v in value.items()}
    if isinstance(value, list | tuple | set):
        return [to_jsonable(v) for v in value]
    return value


def _clamp(limit: int | None) -> int:
    if limit is None:
        return DEFAULT_LIMIT
    return max(1, min(int(limit), MAX_LIMIT))


class SemanticLayer:
    def __init__(
        self, ontology: Ontology, store: GraphStore, sources: dict[str, str] | None = None
    ) -> None:
        self.ontology = ontology
        self.store = store
        self.resolver = TermResolver(ontology)
        self.metrics = MetricEngine(ontology, store, self.resolver)
        self.checker = AnswerabilityChecker(ontology, self.resolver, store)
        self.sources = {"ontology": ontology.name, "ontology_version": ontology.version}
        self.sources.update(sources or {})

    # -- helpers ----------------------------------------------------------------
    def _source(self, **extra: Any) -> dict[str, Any]:
        return {**self.sources, **extra}

    def resolve_concept(self, name: str) -> str:
        """Entity name for a concept name or synonym, or a helpful UnknownConceptError."""
        if name in self.ontology.entities:
            return name
        resolved = self.resolver.resolve_entity(name)
        if resolved:
            return resolved
        known = list(self.ontology.entities)
        close = difflib.get_close_matches(name, known, n=3, cutoff=0.5)
        hint = f" Did you mean: {', '.join(close)}?" if close else ""
        raise UnknownConceptError(
            f"Unknown concept '{name}'. Known concepts: {', '.join(known)}.{hint}"
        )

    def _count(self, entity: str) -> int:
        return sum(1 for _ in self.store.nodes(entity))

    # -- discovery --------------------------------------------------------------
    def list_concepts(self) -> dict[str, Any]:
        concepts = [
            {
                "name": e.name,
                "description": e.description,
                "synonyms": e.synonyms,
                "instances": self._count(e.name),
            }
            for e in self.ontology.entities.values()
        ]
        return {
            "concepts": concepts,
            "relationships": sorted(self.ontology.relationships),
            "metrics": sorted(self.ontology.metrics),
            "source": self._source(),
        }

    def get_concept(self, name: str) -> dict[str, Any]:
        entity = self.ontology.entities[self.resolve_concept(name)]
        return {
            "name": entity.name,
            "description": entity.description,
            "key": entity.key,
            "synonyms": entity.synonyms,
            "properties": [
                {
                    "name": p.name,
                    "type": p.type.value,
                    "required": p.required,
                    "description": p.description,
                }
                for p in entity.properties.values()
            ],
            "relationships": self.get_relationships(entity.name)["relationships"],
            "metrics": [
                m.name for m in self.ontology.metrics.values() if m.definition.entity == entity.name
            ],
            "instances": self._count(entity.name),
            "source": self._source(),
        }

    def search_terms(self, term: str) -> dict[str, Any]:
        matches = [m.to_dict() for m in self.resolver.resolve(term)]
        result: dict[str, Any] = {"term": term, "matches": matches, "source": self._source()}
        if not matches:
            close = difflib.get_close_matches(
                term.lower(), self.resolver.known_terms(), n=3, cutoff=0.6
            )
            result["suggestions"] = close
        return result

    # -- graph ------------------------------------------------------------------
    def get_relationships(self, concept: str) -> dict[str, Any]:
        entity = self.resolve_concept(concept)
        rels = []
        for r in self.ontology.relationships_of(entity):
            direction = "outgoing" if r.from_entity == entity else "incoming"
            if r.from_entity == r.to_entity:
                direction = "self"
            rels.append(
                {
                    "name": r.name,
                    "from": r.from_entity,
                    "to": r.to_entity,
                    "cardinality": r.cardinality.value,
                    "direction": direction,
                    "description": r.description,
                    "synonyms": r.synonyms,
                }
            )
        return {"concept": entity, "relationships": rels, "source": self._source()}

    def find_path(self, from_concept: str, to_concept: str) -> dict[str, Any]:
        a, b = self.resolve_concept(from_concept), self.resolve_concept(to_concept)
        path = concept_path(self.ontology, a, b)
        if path is None:
            return {
                "from": a,
                "to": b,
                "found": False,
                "path": [],
                "hops": None,
                "text": f"No relationship path connects {a} and {b}.",
                "source": self._source(),
            }
        return {"from": a, "to": b, "found": True, **path.to_dict(), "source": self._source()}

    def query_entities(
        self, concept: str, filters: dict[str, Any] | None = None, limit: int | None = DEFAULT_LIMIT
    ) -> dict[str, Any]:
        entity_name = self.resolve_concept(concept)
        entity = self.ontology.entities[entity_name]
        unknown = [f for f in (filters or {}) if f not in entity.properties]
        if unknown:
            raise ValueError(
                f"{entity_name} has no property {', '.join(repr(u) for u in unknown)}. "
                f"Properties: {', '.join(entity.properties)}"
            )
        # Coerce filter values to the property type so "120" compares with 120.0.
        typed: dict[str, Any] = {}
        for field, cond in (filters or {}).items():
            ptype = entity.properties[field].type

            def coerce(v: Any, ptype: Any = ptype) -> Any:
                try:
                    return ptype.coerce(v)
                except (ValueError, TypeError):
                    return v

            if isinstance(cond, dict):
                typed[field] = {
                    op: (
                        [coerce(x) for x in v]
                        if op == "in" and isinstance(v, list)
                        else v
                        if op == "contains"
                        else coerce(v)
                    )
                    for op, v in cond.items()
                }
            else:
                typed[field] = coerce(cond)
        limit = _clamp(limit)
        everything = self.store.query(entity_name, typed)
        shown = everything[:limit]
        return {
            "concept": entity_name,
            "filters": to_jsonable(filters or {}),
            "count": len(everything),
            "returned": len(shown),
            "truncated": len(everything) > len(shown),
            "results": [{"id": n.id, "properties": to_jsonable(n.properties)} for n in shown],
            "source": self._source(),
        }

    def get_neighbors(
        self,
        node_id: str,
        relationship: str | None = None,
        direction: str = "both",
        limit: int | None = DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        if not self.store.has_node(node_id):
            raise NodeNotFoundError(
                f"Node '{node_id}' not found. Node ids look like 'Customer:C001'; "
                f"use query_entities to find them."
            )
        if relationship and relationship not in self.ontology.relationships:
            match = next(
                (m for m in self.resolver.resolve(relationship) if m.kind == "relationship"), None
            )
            if match is None:
                raise ValueError(
                    f"Unknown relationship '{relationship}'. "
                    f"Known: {', '.join(self.ontology.relationships)}"
                )
            relationship = match.target
        limit = _clamp(limit)
        everything = self.store.neighbors(node_id, relationship, direction)  # type: ignore[arg-type]
        shown = everything[:limit]
        node = self.store.get_node(node_id)
        return {
            "node": {
                "id": node.id,
                "concept": node.label,
                "properties": to_jsonable(node.properties),
            },
            "count": len(everything),
            "returned": len(shown),
            "truncated": len(everything) > len(shown),
            "neighbors": [
                {
                    "id": n.node.id,
                    "concept": n.node.label,
                    "relationship": n.edge.label,
                    "direction": n.direction,
                    "properties": to_jsonable(n.node.properties),
                }
                for n in shown
            ],
            "source": self._source(),
        }

    # -- meaning ----------------------------------------------------------------
    def get_metric(self, name: str) -> dict[str, Any]:
        result = self.metrics.compute(name)
        return {**result.to_dict(), "source": self._source()}

    def check_answerable(self, question: str) -> dict[str, Any]:
        return {**self.checker.check(question).to_dict(), "source": self._source()}
