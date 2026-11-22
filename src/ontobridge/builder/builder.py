"""Combine a validated ontology with loaded records to build typed nodes and edges."""

from __future__ import annotations

import datetime as dt
from collections import Counter
from dataclasses import dataclass, field
from typing import Any

from ontobridge.core.errors import GraphBuildError
from ontobridge.core.models import Cardinality, Ontology, PropertyType
from ontobridge.core.records import Dataset, Link, Record
from ontobridge.graph.store import GraphStore

_PY_TYPES: dict[PropertyType, tuple[type, ...]] = {
    PropertyType.STRING: (str,),
    PropertyType.INTEGER: (int,),
    PropertyType.FLOAT: (int, float),
    PropertyType.BOOLEAN: (bool,),
    PropertyType.DATE: (dt.date,),
    PropertyType.DATETIME: (dt.datetime,),
}


@dataclass
class BuildReport:
    """What was written to the graph store."""

    nodes: int = 0
    edges: int = 0
    nodes_by_entity: dict[str, int] = field(default_factory=dict)
    edges_by_relationship: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "nodes": self.nodes,
            "edges": self.edges,
            "nodes_by_entity": self.nodes_by_entity,
            "edges_by_relationship": self.edges_by_relationship,
        }


def _where(item: Record | Link) -> str:
    if item.source and item.row_number is not None:
        return f" ({item.source.rsplit('/', 1)[-1]} row {item.row_number})"
    return ""


class GraphBuilder:
    """Validates every record and link against the ontology, then writes them.

    Nothing is written when any record breaks the ontology: the builder raises one
    :class:`GraphBuildError` listing every problem.
    """

    def __init__(self, ontology: Ontology, store: GraphStore) -> None:
        self.ontology = ontology
        self.store = store

    # -- validation -------------------------------------------------------------
    def _check_record(self, record: Record) -> list[str]:
        entity = self.ontology.entities.get(record.entity)
        where = _where(record)
        if entity is None:
            return [f"record {record.key!r}{where} has unknown entity '{record.entity}'"]
        problems: list[str] = []
        for name in record.properties:
            if name not in entity.properties:
                problems.append(f"{record.entity} {record.key!r}{where}: unknown property '{name}'")
        for name, prop in entity.properties.items():
            value = record.properties.get(name)
            if value is None:
                if prop.required:
                    problems.append(
                        f"{record.entity} {record.key!r}{where}: missing required property '{name}'"
                    )
                continue
            expected = _PY_TYPES[prop.type]
            bad_bool = isinstance(value, bool) and prop.type is not PropertyType.BOOLEAN
            bad_date = prop.type is PropertyType.DATE and isinstance(value, dt.datetime)
            if not isinstance(value, expected) or bad_bool or bad_date:
                problems.append(
                    f"{record.entity} {record.key!r}{where}: property '{name}' should be "
                    f"{prop.type.value}, got {type(value).__name__} {value!r}"
                )
        if record.properties.get(entity.key) != record.key:
            problems.append(
                f"{record.entity} {record.key!r}{where}: key property '{entity.key}' does not "
                f"match record key"
            )
        return problems

    def _check_links(self, dataset: Dataset, node_ids: set[str]) -> list[str]:
        problems: list[str] = []
        for rel_name, links in dataset.links.items():
            rel = self.ontology.relationships.get(rel_name)
            if rel is None:
                problems.append(f"links use unknown relationship '{rel_name}'")
                continue
            out_count: Counter[str] = Counter()
            in_count: Counter[str] = Counter()
            for link in links:
                where = _where(link)
                if link.from_entity != rel.from_entity or link.to_entity != rel.to_entity:
                    problems.append(
                        f"'{rel_name}'{where} must link {rel.from_entity} -> {rel.to_entity}, "
                        f"got {link.from_entity} -> {link.to_entity}"
                    )
                    continue
                missing = [i for i in (link.from_id, link.to_id) if i not in node_ids]
                if missing:
                    problems.append(
                        f"'{rel_name}'{where} points to missing record(s): {', '.join(missing)}"
                    )
                    continue
                out_count[link.from_id] += 1
                in_count[link.to_id] += 1

            card = rel.cardinality
            if card in (Cardinality.ONE_TO_MANY, Cardinality.ONE_TO_ONE):
                for target, n in in_count.items():
                    if n > 1:
                        problems.append(
                            f"cardinality {card.value} of '{rel_name}' broken: {target} has "
                            f"{n} incoming {rel.from_entity} links (max 1)"
                        )
            if card in (Cardinality.MANY_TO_ONE, Cardinality.ONE_TO_ONE):
                for source, n in out_count.items():
                    if n > 1:
                        problems.append(
                            f"cardinality {card.value} of '{rel_name}' broken: {source} has "
                            f"{n} outgoing {rel.to_entity} links (max 1)"
                        )
        return problems

    # -- build ------------------------------------------------------------------
    def build(self, dataset: Dataset) -> BuildReport:
        problems: list[str] = []
        node_ids: set[str] = set()
        for records in dataset.records.values():
            for record in records:
                problems += self._check_record(record)
                if record.node_id in node_ids:
                    problems.append(f"duplicate record {record.node_id}{_where(record)}")
                node_ids.add(record.node_id)
        problems += self._check_links(dataset, node_ids)
        if problems:
            raise GraphBuildError(
                f"{len(problems)} record(s) break the ontology; nothing was written", problems
            )

        report = BuildReport()
        for entity, records in dataset.records.items():
            for record in records:
                self.store.add_node(record.node_id, entity, record.properties)
            report.nodes_by_entity[entity] = len(records)
            report.nodes += len(records)
        for rel_name, links in dataset.links.items():
            for link in links:
                self.store.add_edge(link.from_id, link.to_id, rel_name)
            report.edges_by_relationship[rel_name] = len(links)
            report.edges += len(links)
        return report
