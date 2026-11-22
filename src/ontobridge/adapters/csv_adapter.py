"""CSV input adapter."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Any

from ontobridge.adapters.base import InputAdapter, register_adapter
from ontobridge.core.errors import DataLoadError
from ontobridge.core.records import RawRow, RawTable


@register_adapter("csv")
class CsvAdapter(InputAdapter):
    """Reads a CSV file with a header row. Empty cells become ``None``.

    Row numbers match the line number in the file (the header is line 1).
    """

    extensions = (".csv",)

    def load(self, source: str | Path, **options: Any) -> RawTable:
        path = Path(source)
        if not path.is_file():
            raise DataLoadError(f"CSV file not found: {path}")
        delimiter = options.get("delimiter", ",")
        table = RawTable(source=str(path))
        problems: list[str] = []
        with path.open(newline="", encoding=options.get("encoding", "utf-8-sig")) as fh:
            reader = csv.DictReader(fh, delimiter=delimiter)
            if not reader.fieldnames:
                raise DataLoadError(f"CSV file {path} has no header row")
            header_size = len(reader.fieldnames)
            for row in reader:
                line = reader.line_num
                if None in row or any(v is None for v in row.values()):
                    problems.append(
                        f"{path.name} row {line}: expected {header_size} columns, "
                        f"got {len([v for v in row.values() if v is not None])}"
                    )
                    continue
                values = {
                    k.strip(): (v.strip() if v.strip() != "" else None) for k, v in row.items()
                }
                table.rows.append(RawRow(row_number=line, values=values))
        if problems:
            raise DataLoadError(f"Could not read {path}", problems)
        return table
