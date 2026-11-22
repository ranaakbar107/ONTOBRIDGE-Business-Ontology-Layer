"""KAN-19 and KAN-20: the e-commerce demo domain, end to end."""

from __future__ import annotations

import csv
import json
import subprocess
import sys

from ontobridge import load_project

from .conftest import ECOMMERCE, ROOT


def _rows(name):
    with open(ECOMMERCE / "data" / name, newline="") as fh:
        return list(csv.DictReader(fh))


def test_demo_data_meets_minimum_size():
    assert len(_rows("customers.csv")) >= 10
    assert len(_rows("orders.csv")) >= 30
    assert len(_rows("products.csv")) >= 15
    assert len(json.loads((ECOMMERCE / "data" / "categories.json").read_text())["categories"]) >= 3


def test_demo_ontology_has_required_parts(ontology):
    assert {"Customer", "Order", "Product", "Category"} <= set(ontology.entities)
    assert {"places", "contains"} <= set(ontology.relationships)
    assert "revenue" in ontology.metrics


def test_demo_loads_end_to_end(ontology_path, mapping_path):
    layer, report = load_project(ontology_path, mapping_path)
    assert report.nodes == 59 and report.edges > 0
    assert layer.get_metric("revenue")["value"] > 0


def test_agent_demo_script_answers_three_questions(tmp_path):
    """Runs examples/agent_demo.py: a scripted agent that connects over MCP (stdio)."""
    log = tmp_path / "run.md"
    proc = subprocess.run(
        [sys.executable, str(ROOT / "examples" / "agent_demo.py"), "--log", str(log)],
        capture_output=True,
        text=True,
        timeout=120,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stderr
    text = log.read_text()
    assert "9 tools" in text
    assert "sum of Order.amount where status = paid" in text  # what does revenue mean
    assert "Order:O001" in text  # which orders did Ali place
    assert "Product:" in text  # which products are in them
