"""Metric definitions computed on the graph. Example: revenue = sum of Order.amount where paid."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ontobridge.core.errors import UnknownMetricError
from ontobridge.core.models import Aggregate, Metric, Ontology
from ontobridge.graph.store import GraphStore
from ontobridge.semantic.synonyms import TermResolver


@dataclass(frozen=True)
class MetricResult:
    name: str
    description: str
    formula: str
    entity: str
    value: float | int | None
    records_used: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "formula": self.formula,
            "entity": self.entity,
            "value": self.value,
            "records_used": self.records_used,
        }


class MetricEngine:
    def __init__(
        self, ontology: Ontology, store: GraphStore, resolver: TermResolver | None = None
    ) -> None:
        self.ontology = ontology
        self.store = store
        self.resolver = resolver or TermResolver(ontology)

    def get(self, name: str) -> Metric:
        """Find a metric by name or synonym ("sales" -> revenue)."""
        metric = self.ontology.metrics.get(name)
        if metric is None:
            resolved = self.resolver.resolve_metric(name)
            metric = self.ontology.metrics.get(resolved) if resolved else None
        if metric is None:
            known = ", ".join(sorted(self.ontology.metrics)) or "none"
            raise UnknownMetricError(f"Unknown metric '{name}'. Known metrics: {known}")
        return metric

    def compute(self, name: str) -> MetricResult:
        metric = self.get(name)
        d = metric.definition
        nodes = self.store.query(d.entity, d.filter)
        value: float | int | None
        if d.aggregate is Aggregate.COUNT:
            if d.field:
                value = sum(1 for n in nodes if n.properties.get(d.field) is not None)
            else:
                value = len(nodes)
        else:
            values = [n.properties.get(d.field) for n in nodes]
            values = [v for v in values if v is not None]
            if not values:
                value = 0 if d.aggregate is Aggregate.SUM else None
            elif d.aggregate is Aggregate.SUM:
                value = sum(values)
            elif d.aggregate is Aggregate.AVG:
                value = sum(values) / len(values)
            elif d.aggregate is Aggregate.MIN:
                value = min(values)
            else:
                value = max(values)
        if isinstance(value, float):
            value = round(value, 4)
        return MetricResult(
            name=metric.name,
            description=metric.description,
            formula=metric.formula(),
            entity=d.entity,
            value=value,
            records_used=len(nodes),
        )
