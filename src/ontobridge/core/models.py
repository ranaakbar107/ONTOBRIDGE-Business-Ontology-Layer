"""Typed Pydantic v2 models that represent a business ontology in code.

The ontology has four parts:

* **Entities**     business concepts with typed properties and synonyms
* **Relationships** named, directed links between entities, with cardinality
* **Metrics**      business definitions an agent can resolve, like revenue
* **Synonyms**     business words that resolve to a concept ("buyer" -> Customer)
"""

from __future__ import annotations

import datetime as dt
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ontobridge.core.filters import validate_filter


class PropertyType(StrEnum):
    STRING = "string"
    INTEGER = "integer"
    FLOAT = "float"
    BOOLEAN = "boolean"
    DATE = "date"
    DATETIME = "datetime"

    def coerce(self, value: Any) -> Any:
        """Convert a raw value (often a CSV string) to this type. Raises ValueError."""
        if value is None:
            return None
        if self is PropertyType.STRING:
            return str(value)
        if self is PropertyType.INTEGER:
            if isinstance(value, bool):
                raise ValueError(f"expected integer, got boolean {value!r}")
            if isinstance(value, float) and not value.is_integer():
                raise ValueError(f"expected integer, got {value!r}")
            return int(str(value).strip()) if isinstance(value, str) else int(value)
        if self is PropertyType.FLOAT:
            if isinstance(value, bool):
                raise ValueError(f"expected float, got boolean {value!r}")
            return float(str(value).strip()) if isinstance(value, str) else float(value)
        if self is PropertyType.BOOLEAN:
            if isinstance(value, bool):
                return value
            text = str(value).strip().lower()
            if text in {"true", "1", "yes", "y"}:
                return True
            if text in {"false", "0", "no", "n"}:
                return False
            raise ValueError(f"expected boolean, got {value!r}")
        if self is PropertyType.DATE:
            if isinstance(value, dt.datetime):
                return value.date()
            if isinstance(value, dt.date):
                return value
            return dt.date.fromisoformat(str(value).strip())
        if self is PropertyType.DATETIME:
            if isinstance(value, dt.datetime):
                return value
            return dt.datetime.fromisoformat(str(value).strip())
        raise ValueError(f"unsupported type {self}")  # pragma: no cover


NUMERIC_TYPES = frozenset({PropertyType.INTEGER, PropertyType.FLOAT})


class Cardinality(StrEnum):
    ONE_TO_ONE = "one-to-one"
    ONE_TO_MANY = "one-to-many"
    MANY_TO_ONE = "many-to-one"
    MANY_TO_MANY = "many-to-many"


class Aggregate(StrEnum):
    SUM = "sum"
    COUNT = "count"
    AVG = "avg"
    MIN = "min"
    MAX = "max"


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class Property(_Strict):
    """A typed property of an entity."""

    name: str
    type: PropertyType = PropertyType.STRING
    description: str = ""
    required: bool = True


class Entity(_Strict):
    """A business concept, e.g. Customer."""

    name: str
    description: str = ""
    key: str = "id"
    synonyms: list[str] = Field(default_factory=list)
    properties: dict[str, Property] = Field(default_factory=dict)

    @field_validator("properties", mode="before")
    @classmethod
    def _expand_properties(cls, value: Any) -> Any:
        """Allow the short YAML form ``email: string`` next to the full mapping form."""
        if not isinstance(value, dict):
            return value
        expanded: dict[str, Any] = {}
        for prop_name, spec in value.items():
            if isinstance(spec, str):
                expanded[prop_name] = {"name": prop_name, "type": spec}
            elif isinstance(spec, dict):
                expanded[prop_name] = {"name": prop_name, **spec}
            else:
                expanded[prop_name] = spec
        return expanded

    @model_validator(mode="after")
    def _key_is_a_property(self) -> Entity:
        if not self.properties:
            raise ValueError(f"entity '{self.name}' must declare at least one property")
        if self.key not in self.properties:
            raise ValueError(
                f"entity '{self.name}' uses key '{self.key}' but has no property named "
                f"'{self.key}' (properties: {', '.join(self.properties)})"
            )
        return self


class Relationship(_Strict):
    """A named, directed relationship: ``from_entity --name--> to_entity``."""

    name: str
    from_entity: str = Field(alias="from")
    to_entity: str = Field(alias="to")
    cardinality: Cardinality
    description: str = ""
    synonyms: list[str] = Field(default_factory=list)


class MetricDefinition(_Strict):
    entity: str
    aggregate: Aggregate
    field: str | None = None
    filter: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _field_required_unless_count(self) -> MetricDefinition:
        if self.aggregate is not Aggregate.COUNT and not self.field:
            raise ValueError(f"aggregate '{self.aggregate.value}' needs a 'field'")
        return self


class Metric(_Strict):
    """A business definition an agent can resolve, e.g. revenue."""

    name: str
    description: str = ""
    synonyms: list[str] = Field(default_factory=list)
    definition: MetricDefinition

    def formula(self) -> str:
        """The definition in plain words, e.g. ``sum of Order.amount where status = paid``."""
        d = self.definition
        target = f"{d.entity}.{d.field}" if d.field else f"{d.entity} records"
        text = f"{d.aggregate.value} of {target}"
        if d.filter:
            parts = []
            for field, cond in d.filter.items():
                if isinstance(cond, dict):
                    parts += [f"{field} {op} {val}" for op, val in cond.items()]
                else:
                    parts.append(f"{field} = {cond}")
            text += " where " + " and ".join(parts)
        return text


class Synonym(_Strict):
    """A business word that resolves to a concept, relationship or metric."""

    term: str
    target: str
    kind: str  # "entity" | "relationship" | "metric"


class Ontology(_Strict):
    """The whole business ontology. Validated on construction: it fails fast."""

    name: str = "ontology"
    version: str = "1.0"
    description: str = ""
    entities: dict[str, Entity] = Field(default_factory=dict)
    relationships: dict[str, Relationship] = Field(default_factory=dict)
    metrics: dict[str, Metric] = Field(default_factory=dict)

    @field_validator("entities", "relationships", "metrics", mode="before")
    @classmethod
    def _inject_names(cls, value: Any) -> Any:
        """In YAML the name is the mapping key; copy it into each item."""
        if not isinstance(value, dict):
            return value
        return {
            key: ({"name": key, **spec} if isinstance(spec, dict) else spec)
            for key, spec in value.items()
        }

    @model_validator(mode="after")
    def _cross_references(self) -> Ontology:
        problems: list[str] = []
        if not self.entities:
            problems.append("ontology must define at least one entity")

        for rel in self.relationships.values():
            for side, entity_name in (("from", rel.from_entity), ("to", rel.to_entity)):
                if entity_name not in self.entities:
                    problems.append(
                        f"relationship '{rel.name}' refers to unknown entity '{entity_name}' "
                        f"in '{side}' (known entities: {', '.join(self.entities) or 'none'})"
                    )

        for metric in self.metrics.values():
            d = metric.definition
            entity = self.entities.get(d.entity)
            if entity is None:
                problems.append(f"metric '{metric.name}' refers to unknown entity '{d.entity}'")
                continue
            if d.field and d.field not in entity.properties:
                problems.append(
                    f"metric '{metric.name}' uses missing property '{d.field}' on '{d.entity}'"
                )
            elif (
                d.field
                and d.aggregate in {Aggregate.SUM, Aggregate.AVG}
                and entity.properties[d.field].type not in NUMERIC_TYPES
            ):
                problems.append(
                    f"metric '{metric.name}' uses '{d.aggregate.value}' on non-numeric "
                    f"property '{d.entity}.{d.field}'"
                )
            for field in d.filter:
                if field not in entity.properties:
                    problems.append(
                        f"metric '{metric.name}' filters on missing property "
                        f"'{field}' of '{d.entity}'"
                    )
            problems += [f"metric '{metric.name}': {p}" for p in validate_filter(d.filter)]

        # Every business word must resolve to exactly one thing.
        seen: dict[str, str] = {}
        for syn in self.synonym_index(check=False):
            key = syn.term.lower()
            owner = f"{syn.kind} '{syn.target}'"
            if key in seen and seen[key] != owner:
                problems.append(f"term '{syn.term}' is used by both {seen[key]} and {owner}")
            seen.setdefault(key, owner)

        if problems:
            raise ValueError("; ".join(problems))
        return self

    def synonym_index(self, check: bool = True) -> list[Synonym]:
        """Every resolvable term: names and synonyms of entities, relationships and metrics."""
        items: list[Synonym] = []
        for e in self.entities.values():
            items.append(Synonym(term=e.name, target=e.name, kind="entity"))
            items += [Synonym(term=s, target=e.name, kind="entity") for s in e.synonyms]
        for r in self.relationships.values():
            items.append(Synonym(term=r.name, target=r.name, kind="relationship"))
            items += [Synonym(term=s, target=r.name, kind="relationship") for s in r.synonyms]
        for m in self.metrics.values():
            items.append(Synonym(term=m.name, target=m.name, kind="metric"))
            items += [Synonym(term=s, target=m.name, kind="metric") for s in m.synonyms]
        return items

    def relationships_of(self, entity: str) -> list[Relationship]:
        return [
            r
            for r in self.relationships.values()
            if r.from_entity == entity or r.to_entity == entity
        ]
