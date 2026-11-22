"""Map raw rows from CSV/JSON files to typed ontology records and links.

The mapping lives in its own YAML file so the ontology stays about meaning
and the mapping stays about where the data is::

    data_dir: data                 # relative to this mapping file
    entities:
      Customer:
        source: customers.csv
        columns: {customer_name: name}   # optional: file column -> property
      Category:
        source: categories.json
        path: items                      # optional: JSON key holding the list
    relationships:
      places:
        source: orders.csv
        from: customer_id   # column with the key of the 'from' entity (Customer)
        to: id              # column with the key of the 'to' entity (Order)

A blank ``from`` or ``to`` cell means "no link" for that row. Every other
problem is reported with its file and row number; no row is dropped silently.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from ontobridge.adapters.base import adapter_for_path, get_adapter
from ontobridge.core.errors import DataLoadError
from ontobridge.core.models import Ontology
from ontobridge.core.records import Dataset, Link, RawTable, Record


class EntitySource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source: str
    format: str | None = None
    path: str | None = None
    columns: dict[str, str] = Field(default_factory=dict)


class RelationshipSource(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    source: str
    format: str | None = None
    path: str | None = None
    from_column: str = Field(alias="from")
    to_column: str = Field(alias="to")


class DataMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    data_dir: str = "."
    entities: dict[str, EntitySource] = Field(default_factory=dict)
    relationships: dict[str, RelationshipSource] = Field(default_factory=dict)


def load_mapping(path: str | Path) -> tuple[DataMapping, Path]:
    """Read a mapping YAML file. Returns the mapping and the resolved data directory."""
    path = Path(path)
    if not path.is_file():
        raise DataLoadError(f"Mapping file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        mapping = DataMapping.model_validate(raw)
    except yaml.YAMLError as exc:
        raise DataLoadError(f"Invalid YAML in mapping {path}: {exc}") from None
    except ValidationError as exc:
        errors = [f"{'.'.join(map(str, e['loc']))}: {e['msg']}" for e in exc.errors()]
        raise DataLoadError(f"Invalid mapping {path}", errors) from None
    return mapping, (path.parent / mapping.data_dir).resolve()


def _read(source: str, fmt: str | None, json_path: str | None, data_dir: Path) -> RawTable:
    file_path = Path(source)
    if not file_path.is_absolute():
        file_path = data_dir / file_path
    adapter = get_adapter(fmt) if fmt else adapter_for_path(file_path)
    options = {"path": json_path} if json_path else {}
    return adapter.load(file_path, **options)


def _check_mapping(ontology: Ontology, mapping: DataMapping) -> list[str]:
    problems: list[str] = []
    for name, spec in mapping.entities.items():
        entity = ontology.entities.get(name)
        if entity is None:
            problems.append(f"mapping refers to unknown entity '{name}'")
            continue
        for column, prop in spec.columns.items():
            if prop not in entity.properties:
                problems.append(
                    f"mapping for '{name}' maps column '{column}' to missing property '{prop}'"
                )
    for name in mapping.relationships:
        if name not in ontology.relationships:
            problems.append(f"mapping refers to unknown relationship '{name}'")
    return problems


def map_records(
    ontology: Ontology, entity_name: str, table: RawTable, columns: dict[str, str] | None = None
) -> list[Record]:
    """Turn raw rows into typed records. Collects every bad row, then raises once."""
    entity = ontology.entities[entity_name]
    columns = columns or {}
    file_name = Path(table.source).name
    records: list[Record] = []
    problems: list[str] = []
    seen_keys: dict[Any, int] = {}

    for row in table.rows:
        values = {columns.get(col, col): val for col, val in row.values.items()}
        props: dict[str, Any] = {}
        row_problems: list[str] = []
        for prop_name, prop in entity.properties.items():
            raw = values.get(prop_name)
            if raw is None or raw == "":
                if prop.required:
                    row_problems.append(f"missing required property '{prop_name}'")
                props[prop_name] = None
                continue
            try:
                props[prop_name] = prop.type.coerce(raw)
            except (ValueError, TypeError) as exc:
                row_problems.append(
                    f"property '{prop_name}' expects {prop.type.value}, got {raw!r} ({exc})"
                )
        key = props.get(entity.key)
        if not row_problems and key is not None:
            if key in seen_keys:
                row_problems.append(
                    f"duplicate key {entity.key}={key!r} (first seen in row {seen_keys[key]})"
                )
            else:
                seen_keys[key] = row.row_number
        if row_problems:
            problems += [f"{file_name} row {row.row_number}: {p}" for p in row_problems]
            continue
        records.append(
            Record(
                entity=entity_name,
                key=key,
                properties=props,
                source=table.source,
                row_number=row.row_number,
            )
        )
    if problems:
        raise DataLoadError(f"{len(problems)} problem(s) loading '{entity_name}'", problems)
    return records


def map_links(
    ontology: Ontology, rel_name: str, table: RawTable, from_column: str, to_column: str
) -> list[Link]:
    rel = ontology.relationships[rel_name]
    from_key = ontology.entities[rel.from_entity].properties[ontology.entities[rel.from_entity].key]
    to_key = ontology.entities[rel.to_entity].properties[ontology.entities[rel.to_entity].key]
    file_name = Path(table.source).name
    links: list[Link] = []
    problems: list[str] = []
    for row in table.rows:
        missing = [c for c in (from_column, to_column) if c not in row.values]
        if missing:
            problems += [f"{file_name} row {row.row_number}: missing column '{c}'" for c in missing]
            continue
        raw_from, raw_to = row.values.get(from_column), row.values.get(to_column)
        if raw_from in (None, "") or raw_to in (None, ""):
            continue  # documented: a blank cell means "no link"
        try:
            links.append(
                Link(
                    relationship=rel_name,
                    from_entity=rel.from_entity,
                    from_key=from_key.type.coerce(raw_from),
                    to_entity=rel.to_entity,
                    to_key=to_key.type.coerce(raw_to),
                    source=table.source,
                    row_number=row.row_number,
                )
            )
        except (ValueError, TypeError) as exc:
            problems.append(f"{file_name} row {row.row_number}: bad key for '{rel_name}' ({exc})")
    if problems:
        raise DataLoadError(f"{len(problems)} problem(s) loading '{rel_name}'", problems)
    return links


def load_dataset(ontology: Ontology, mapping_path: str | Path) -> Dataset:
    """Load every file named in the mapping and return typed records and links."""
    mapping, data_dir = load_mapping(mapping_path)
    problems = _check_mapping(ontology, mapping)
    if problems:
        raise DataLoadError(f"Mapping {mapping_path} does not match the ontology", problems)

    dataset = Dataset()
    all_problems: list[str] = []
    for name, spec in mapping.entities.items():
        try:
            table = _read(spec.source, spec.format, spec.path, data_dir)
            dataset.add_records(name, map_records(ontology, name, table, spec.columns))
        except DataLoadError as exc:
            all_problems += exc.row_errors or [str(exc)]
    for name, spec in mapping.relationships.items():
        try:
            table = _read(spec.source, spec.format, spec.path, data_dir)
            dataset.add_links(
                name, map_links(ontology, name, table, spec.from_column, spec.to_column)
            )
        except DataLoadError as exc:
            all_problems += exc.row_errors or [str(exc)]
    if all_problems:
        raise DataLoadError("Data could not be loaded", all_problems)
    return dataset
