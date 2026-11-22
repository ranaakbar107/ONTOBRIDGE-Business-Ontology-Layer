"""JSON input adapter."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ontobridge.adapters.base import InputAdapter, register_adapter
from ontobridge.core.errors import DataLoadError
from ontobridge.core.records import RawRow, RawTable


@register_adapter("json")
class JsonAdapter(InputAdapter):
    """Reads a JSON array of objects, or an object holding that array under ``path``.

    Row numbers are 1-based positions in the array.
    """

    extensions = (".json",)

    def load(self, source: str | Path, **options: Any) -> RawTable:
        path = Path(source)
        if not path.is_file():
            raise DataLoadError(f"JSON file not found: {path}")
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise DataLoadError(f"Invalid JSON in {path}: {exc}") from None

        key = options.get("path")
        if key:
            for part in str(key).split("."):
                if not isinstance(data, dict) or part not in data:
                    raise DataLoadError(f"JSON file {path} has no key '{key}'")
                data = data[part]
        if not isinstance(data, list):
            raise DataLoadError(
                f"JSON file {path} must contain a list of objects"
                + ("" if key else " (or set 'path' to the key that holds it)")
            )

        table = RawTable(source=str(path))
        problems: list[str] = []
        for index, item in enumerate(data, start=1):
            if not isinstance(item, dict):
                problems.append(f"{path.name} row {index}: expected an object, got {item!r}")
                continue
            table.rows.append(RawRow(row_number=index, values=dict(item)))
        if problems:
            raise DataLoadError(f"Could not read {path}", problems)
        return table
