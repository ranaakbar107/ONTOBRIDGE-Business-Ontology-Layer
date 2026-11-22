"""Resolve business words to ontology concepts using their names and synonyms."""

from __future__ import annotations

import re
from dataclasses import dataclass

from ontobridge.core.models import Ontology

_NON_WORD = re.compile(r"[^a-z0-9 ]+")
_SPACES = re.compile(r"\s+")


def singular(word: str) -> str:
    """Very small English singularizer for simple plurals: orders, categories, boxes."""
    if len(word) <= 3:
        return word
    if word.endswith("ies"):
        return word[:-3] + "y"
    if word.endswith(("sses", "shes", "ches", "xes", "zes")):
        return word[:-2]
    if word.endswith("s") and not word.endswith(("ss", "us", "is")):
        return word[:-1]
    return word


def normalize(term: str) -> str:
    """Lower-case, drop punctuation, collapse spaces and singularize each word.

    ``"Buyers"`` -> ``"buyer"``, ``"Product_Categories"`` -> ``"product category"``.
    """
    text = term.replace("_", " ").replace("-", " ")
    # split CamelCase: OrderItem -> order item
    text = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", text).lower()
    text = _SPACES.sub(" ", _NON_WORD.sub(" ", text)).strip()
    return " ".join(singular(w) for w in text.split(" ")) if text else ""


@dataclass(frozen=True)
class TermMatch:
    term: str
    target: str
    kind: str  # entity | relationship | metric
    matched_on: str  # the name or synonym that matched

    def to_dict(self) -> dict[str, str]:
        return {
            "term": self.term,
            "target": self.target,
            "kind": self.kind,
            "matched_on": self.matched_on,
        }


class TermResolver:
    """Index of every name and synonym in the ontology."""

    def __init__(self, ontology: Ontology) -> None:
        self.ontology = ontology
        self._index: dict[str, list[tuple[str, str, str]]] = {}
        for syn in ontology.synonym_index():
            key = normalize(syn.term)
            entry = (syn.target, syn.kind, syn.term)
            bucket = self._index.setdefault(key, [])
            if not any(e[0] == syn.target and e[1] == syn.kind for e in bucket):
                bucket.append(entry)
        self.max_words = max((len(k.split()) for k in self._index), default=1)

    def resolve(self, term: str) -> list[TermMatch]:
        """All concepts a word resolves to. Unknown words return an empty list."""
        key = normalize(term)
        return [
            TermMatch(term=term, target=target, kind=kind, matched_on=original)
            for target, kind, original in self._index.get(key, [])
        ]

    def resolve_entity(self, term: str) -> str | None:
        """Name of the entity a word refers to, or None."""
        for match in self.resolve(term):
            if match.kind == "entity":
                return match.target
        return None

    def resolve_metric(self, term: str) -> str | None:
        for match in self.resolve(term):
            if match.kind == "metric":
                return match.target
        return None

    def known_terms(self) -> list[str]:
        return sorted(self._index)
