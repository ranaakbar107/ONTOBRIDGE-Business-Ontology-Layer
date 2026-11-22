"""KAN-13: CSV and JSON data loaders (input adapters) with a mapping file."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

import pytest

from ontobridge.adapters import CsvAdapter, JsonAdapter, get_adapter, load_dataset
from ontobridge.adapters.mapping import map_records
from ontobridge.core.errors import DataLoadError


def test_csv_and_json_are_registered():
    assert isinstance(get_adapter("csv"), CsvAdapter)
    assert isinstance(get_adapter("json"), JsonAdapter)


def test_csv_adapter_reads_rows_with_line_numbers(tmp_path: Path):
    f = tmp_path / "c.csv"
    f.write_text("id,name\n1,Ali\n2,\n")
    table = CsvAdapter().load(f)
    assert [r.row_number for r in table.rows] == [2, 3]
    assert table.rows[1].values == {"id": "2", "name": None}


def test_csv_adapter_reports_ragged_rows(tmp_path: Path):
    f = tmp_path / "c.csv"
    f.write_text("id,name\n1,Ali\n2\n3,Sara,extra\n")
    with pytest.raises(DataLoadError) as info:
        CsvAdapter().load(f)
    assert "row 3" in str(info.value) and "row 4" in str(info.value)


def test_json_adapter_with_path_and_errors(tmp_path: Path):
    f = tmp_path / "c.json"
    f.write_text(json.dumps({"data": {"items": [{"id": "A"}, {"id": "B"}]}}))
    assert [r.values["id"] for r in JsonAdapter().load(f, path="data.items").rows] == ["A", "B"]
    with pytest.raises(DataLoadError, match="list of objects"):
        JsonAdapter().load(f)
    bad = tmp_path / "bad.json"
    bad.write_text('[{"id": 1}, 5]')
    with pytest.raises(DataLoadError, match="row 2"):
        JsonAdapter().load(bad)
    broken = tmp_path / "broken.json"
    broken.write_text("{not json")
    with pytest.raises(DataLoadError, match="Invalid JSON"):
        JsonAdapter().load(broken)


def test_ecommerce_dataset_loads_typed_records(ontology, mapping_path):
    ds = load_dataset(ontology, mapping_path)
    assert {k: len(v) for k, v in ds.records.items()} == {
        "Customer": 10,
        "Order": 30,
        "Product": 15,
        "Category": 4,
    }
    order = next(r for r in ds.records["Order"] if r.key == "O001")
    assert order.properties["amount"] == 118.0
    assert order.properties["order_date"] == dt.date(2026, 1, 3)
    assert order.row_number == 2
    assert {len(v) for v in ds.links.values()} and len(ds.links["places"]) == 30
    product = next(r for r in ds.records["Product"] if r.key == "P004")
    assert product.properties["in_stock"] is False


def _write_project(tmp_path: Path, orders_csv: str, extra_mapping: str = "") -> Path:
    (tmp_path / "orders.csv").write_text(orders_csv)
    (tmp_path / "customers.csv").write_text("id,name\nC1,Ali\nC2,Sara\n")
    mapping = tmp_path / "mapping.yaml"
    mapping.write_text(
        "entities:\n"
        "  Customer: {source: customers.csv}\n"
        "  Order: {source: orders.csv, columns: {order_id: id}}\n"
        "relationships:\n"
        "  places: {source: orders.csv, from: customer_id, to: order_id}\n" + extra_mapping
    )
    return mapping


def test_column_mapping_is_declared_in_mapping_file(minimal_dict, tmp_path):
    from ontobridge.core.models import Ontology

    onto = Ontology.model_validate(minimal_dict)
    mapping = _write_project(
        tmp_path, "order_id,customer_id,amount,status\nO1,C1,10.5,paid\nO2,,3,paid\n"
    )
    ds = load_dataset(onto, mapping)
    assert [r.key for r in ds.records["Order"]] == ["O1", "O2"]
    # blank customer_id = no link for that order (documented behaviour)
    assert [(link.from_id, link.to_id) for link in ds.links["places"]] == [
        ("Customer:C1", "Order:O1")
    ]


def test_bad_rows_are_reported_with_row_numbers_never_dropped(minimal_dict, tmp_path):
    from ontobridge.core.models import Ontology

    onto = Ontology.model_validate(minimal_dict)
    mapping = _write_project(
        tmp_path,
        "order_id,customer_id,amount,status\n"
        "O1,C1,10.5,paid\n"
        "O2,C1,ten,paid\n"  # row 3: bad float
        "O3,C2,4,\n"  # row 4: missing required status
        "O1,C2,1,paid\n",  # row 5: duplicate key
    )
    with pytest.raises(DataLoadError) as info:
        load_dataset(onto, mapping)
    text = str(info.value)
    assert "orders.csv row 3" in text and "expects float" in text
    assert "orders.csv row 4" in text and "missing required property 'status'" in text
    assert "orders.csv row 5" in text and "duplicate key" in text
    assert len(info.value.row_errors) == 3


def test_mapping_must_match_ontology(minimal_dict, tmp_path):
    from ontobridge.core.models import Ontology

    onto = Ontology.model_validate(minimal_dict)
    mapping = _write_project(
        tmp_path,
        "order_id,customer_id,amount,status\nO1,C1,1,paid\n",
        "  ships: {source: orders.csv, from: a, to: b}\n",
    )
    with pytest.raises(DataLoadError, match="unknown relationship 'ships'"):
        load_dataset(onto, mapping)


def test_map_records_with_renamed_columns(ontology):
    from ontobridge.core.records import RawRow, RawTable

    table = RawTable(
        "x.csv",
        [RawRow(2, {"cid": "C9", "name": "Zed", "email": "z@x.io", "signup_date": "2026-02-01"})],
    )
    (rec,) = map_records(ontology, "Customer", table, {"cid": "id"})
    assert rec.node_id == "Customer:C9" and rec.properties["city"] is None
