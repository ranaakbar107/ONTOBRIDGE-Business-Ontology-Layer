"""Tell an agent whether the ontology can answer a question, and which terms are missing."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from ontobridge.core.models import Ontology
from ontobridge.graph.store import GraphStore
from ontobridge.semantic.synonyms import TermResolver, normalize

# Question words and generic analytics words that carry no business meaning.
STOPWORDS = frozenset(
    """
    a about above after all also am an and any are as at be been before being below
    between both but by can could did do does doing done down during each either else
    ever every for from further get gets give had has have having he her here hers him
    his how i if in into is it its itself just let list lists me mean means meaning more
    most much my no nor not now of off on once only or other our ours out over own per
    please same she should show shows so some such than that the their theirs them then
    there these they this those through to too under until up us very was we were what
    when where which while who whom whose why will with would you your yours tell find
    give gave many number total totals count top bottom last first latest recent average
    avg sum min max highest lowest biggest smallest across overall exist exists made
    make happen happened like vs versus against whats data record records info
    information detail details definition defined define describe live lives living
    located based come comes belong belongs want need see know compare today yesterday
    tomorrow day days week weeks month months quarter quarters year years ago since
    current currently now recently time times date dates
    """.split()  # noqa: SIM905
)

_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9_']*|\d+(?:\.\d+)?")


@dataclass
class AnswerabilityResult:
    question: str
    answerable: bool
    coverage: float
    matched: list[dict[str, str]] = field(default_factory=list)
    missing_terms: list[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answerable": self.answerable,
            "coverage": self.coverage,
            "matched": self.matched,
            "missing_terms": self.missing_terms,
            "reason": self.reason,
        }


class AnswerabilityChecker:
    """Matches the words of a question against concepts, relationships, metrics,
    property names and (optionally) values present in the graph."""

    def __init__(
        self,
        ontology: Ontology,
        resolver: TermResolver | None = None,
        store: GraphStore | None = None,
    ) -> None:
        self.ontology = ontology
        self.resolver = resolver or TermResolver(ontology)
        self.store = store
        self._properties = {
            normalize(p): (entity.name, p)
            for entity in ontology.entities.values()
            for p in entity.properties
        }
        self._values: set[str] | None = None

    def _value_words(self) -> set[str]:
        """Lower-case words that appear in string property values, e.g. 'ali', 'paid'."""
        if self._values is None:
            words: set[str] = set()
            if self.store is not None:
                for node in self.store.nodes():
                    for value in node.properties.values():
                        if isinstance(value, str):
                            for token in _TOKEN.findall(value.lower()):
                                words.add(token)
                                words.add(normalize(token))
            self._values = words
        return self._values

    def check(self, question: str) -> AnswerabilityResult:
        tokens = [t.lower().replace("'s", "").strip("'") for t in _TOKEN.findall(question)]
        matched: list[dict[str, str]] = []
        missing: list[str] = []
        i = 0
        while i < len(tokens):
            # Longest multi-word term first, e.g. "order line" or "ad spend".
            hit = None
            for size in range(min(self.resolver.max_words, len(tokens) - i), 0, -1):
                phrase = " ".join(tokens[i : i + size])
                matches = self.resolver.resolve(phrase)
                if matches:
                    hit = (size, matches)
                    break
            if hit:
                size, matches = hit
                matched += [m.to_dict() for m in matches]
                i += size
                continue

            token = tokens[i]
            i += 1
            if not token or token in STOPWORDS or normalize(token) in STOPWORDS:
                continue
            if token.replace(".", "", 1).isdigit():
                matched.append(
                    {"term": token, "target": token, "kind": "value", "matched_on": "number"}
                )
                continue
            prop = self._properties.get(normalize(token))
            if prop:
                matched.append(
                    {
                        "term": token,
                        "target": f"{prop[0]}.{prop[1]}",
                        "kind": "property",
                        "matched_on": prop[1],
                    }
                )
                continue
            if token in self._value_words() or normalize(token) in self._value_words():
                matched.append(
                    {"term": token, "target": token, "kind": "value", "matched_on": "graph value"}
                )
                continue
            if token not in missing:
                missing.append(token)

        meaningful = len(matched) + len(missing)
        coverage = round(len(matched) / meaningful, 3) if meaningful else 0.0
        has_concept = any(m["kind"] in {"entity", "metric", "relationship"} for m in matched)
        answerable = has_concept and not missing
        if answerable:
            reason = "Every business term in the question is covered by the ontology."
        elif missing:
            reason = (
                "The ontology does not define: "
                + ", ".join(missing)
                + ". Add them as entities, properties, metrics or synonyms."
            )
        else:
            reason = "The question does not mention any concept, relationship or metric."
        return AnswerabilityResult(
            question=question,
            answerable=answerable,
            coverage=coverage,
            matched=matched,
            missing_terms=missing,
            reason=reason,
        )
