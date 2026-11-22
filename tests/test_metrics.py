"""KAN-15: Metric definition and calculation engine."""

from __future__ import annotations

import csv

import pytest

from ontobridge.core.errors import UnknownMetricError
from ontobridge.semantic import MetricEngine

from .conftest import ECOMMERCE


def _orders():
    with open(ECOMMERCE / "data" / "orders.csv", newline="") as fh:
        return list(csv.DictReader(fh))


def test_revenue_matches_demo_data(layer):
    expected = round(sum(float(o["amount"]) for o in _orders() if o["status"] == "paid"), 4)
    result = layer.metrics.compute("revenue")
    assert result.value == pytest.approx(expected)
    assert result.records_used == sum(1 for o in _orders() if o["status"] == "paid")


def test_metric_returns_description_and_formula_in_plain_words(layer):
    r = layer.metrics.compute("revenue")
    assert "paid" in r.description.lower()
    assert r.formula == "sum of Order.amount where status = paid"


def test_count_avg_and_synonym(layer):
    assert layer.metrics.compute("order_count").value == len(_orders())
    paid = [float(o["amount"]) for o in _orders() if o["status"] == "paid"]
    assert layer.metrics.compute("aov").value == pytest.approx(sum(paid) / len(paid), rel=1e-3)
    assert layer.metrics.compute("sales").name == "revenue"


def test_unknown_metric_has_clear_error(layer):
    with pytest.raises(UnknownMetricError, match="Unknown metric 'profit'. Known metrics:"):
        layer.metrics.compute("profit")


def test_min_max_and_empty(ontology):
    from ontobridge.graph import InMemoryGraphStore

    store = InMemoryGraphStore()
    engine = MetricEngine(ontology, store)
    assert engine.compute("revenue").value == 0  # no data: sum is 0
    assert engine.compute("average_order_value").value is None
    store.add_node("Order:1", "Order", {"amount": 5.0, "status": "paid"})
    store.add_node("Order:2", "Order", {"amount": 7.0, "status": "paid"})
    assert engine.compute("revenue").value == 12.0
