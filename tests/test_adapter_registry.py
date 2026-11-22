"""KAN-26: InputAdapter base interface and registry."""

from __future__ import annotations

from pathlib import Path

import pytest

from ontobridge.adapters import (
    CsvAdapter,
    InputAdapter,
    JsonAdapter,
    YamlOntologyAdapter,
    adapter_for_path,
    available_adapters,
    get_adapter,
    register_adapter,
    unregister_adapter,
)
from ontobridge.core.errors import AdapterNotFoundError
from ontobridge.core.records import RawRow, RawTable


def test_input_adapter_is_abstract():
    with pytest.raises(TypeError):
        InputAdapter()  # type: ignore[abstract]


@pytest.mark.parametrize(
    ("name", "cls"),
    [
        ("yaml", YamlOntologyAdapter),
        ("csv", CsvAdapter),
        ("json", JsonAdapter),
        ("CSV", CsvAdapter),
    ],
)
def test_registry_resolves_adapter_by_name(name, cls):
    assert isinstance(get_adapter(name), cls)


def test_registry_lists_builtin_adapters():
    assert {"yaml", "csv", "json"} <= set(available_adapters())


def test_unknown_adapter_has_clear_error():
    with pytest.raises(AdapterNotFoundError, match="No input adapter registered for 'xml'"):
        get_adapter("xml")


def test_adapter_for_path_uses_extension():
    assert isinstance(adapter_for_path("orders.csv"), CsvAdapter)
    assert isinstance(adapter_for_path("onto.yml"), YamlOntologyAdapter)
    with pytest.raises(AdapterNotFoundError):
        adapter_for_path("data.parquet")


def test_new_format_can_be_added_without_changing_core(tmp_path: Path):
    """A dummy adapter proves a new format plugs in through the registry only."""

    @register_adapter("pipe")
    class PipeAdapter(InputAdapter):
        extensions = (".pipe",)

        def load(self, source, **options):
            lines = Path(source).read_text().splitlines()
            header = lines[0].split("|")
            rows = [
                RawRow(i, dict(zip(header, line.split("|"), strict=True)))
                for i, line in enumerate(lines[1:], start=2)
            ]
            return RawTable(source=str(source), rows=rows)

    try:
        f = tmp_path / "people.pipe"
        f.write_text("id|name\n1|Ali\n2|Sara\n")
        table = get_adapter("pipe").load(f)
        assert [r.values["name"] for r in table.rows] == ["Ali", "Sara"]
        assert isinstance(adapter_for_path(f), PipeAdapter)
    finally:
        unregister_adapter("pipe")
    assert "pipe" not in available_adapters()


def test_register_rejects_non_adapter():
    with pytest.raises(TypeError):
        register_adapter("bad")(object)  # type: ignore[arg-type]
