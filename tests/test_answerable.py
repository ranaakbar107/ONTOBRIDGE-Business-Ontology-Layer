"""KAN-17: Question answerability checker."""

from __future__ import annotations

import pytest

from ontobridge.semantic import AnswerabilityChecker


@pytest.mark.parametrize(
    "question",
    [
        "What does revenue mean?",
        "Which orders did Ali place?",
        "Which products are in them?",
        "How many buyers live in Lahore?",
        "List paid orders with amount over 100",
        "What is the average order value?",
    ],
)
def test_known_questions_are_answerable(layer, question):
    result = layer.check_answerable(question)
    assert result["answerable"], result
    assert result["missing_terms"] == []
    assert result["coverage"] == 1.0


def test_known_terms_are_listed(layer):
    result = layer.check_answerable("Show revenue for clients")
    targets = {(m["kind"], m["target"]) for m in result["matched"]}
    assert ("metric", "revenue") in targets and ("entity", "Customer") in targets


def test_unknown_term_is_not_answerable_and_named(layer):
    result = layer.check_answerable("How much ad spend did we have last month?")
    assert result["answerable"] is False
    assert result["missing_terms"] == ["ad", "spend"]
    assert "ad, spend" in result["reason"]


def test_coverage_is_between_zero_and_one(layer):
    partial = layer.check_answerable("What is the churn of customers?")
    assert 0 < partial["coverage"] < 1 and partial["missing_terms"] == ["churn"]
    none = layer.check_answerable("weather forecast")
    assert none["coverage"] == 0.0 and not none["answerable"]


def test_question_without_concepts(layer):
    result = layer.check_answerable("hello?")
    assert not result["answerable"]
    assert result["coverage"] == 0.0


def test_works_without_a_graph(ontology):
    checker = AnswerabilityChecker(ontology)
    assert checker.check("revenue by customer").answerable
    # without a graph, data values like names are unknown
    assert checker.check("orders of Ali").missing_terms == ["ali"]
