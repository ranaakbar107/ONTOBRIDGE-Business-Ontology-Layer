"""Error types. Every error carries a human readable message that names the problem."""

from __future__ import annotations


class OntoBridgeError(Exception):
    """Base class for all ontobridge errors."""


class OntologyValidationError(OntoBridgeError):
    """The ontology definition is invalid (unknown entity, bad cardinality, missing property...)."""

    def __init__(self, message: str, errors: list[str] | None = None) -> None:
        self.errors = errors or [message]
        super().__init__(message)


class AdapterNotFoundError(OntoBridgeError):
    """No input adapter is registered under the requested name."""


class DataLoadError(OntoBridgeError):
    """A data file could not be loaded. Lists every bad row with its row number."""

    def __init__(self, message: str, row_errors: list[str] | None = None) -> None:
        self.row_errors = row_errors or []
        if self.row_errors:
            message = message + "\n" + "\n".join(f"  - {e}" for e in self.row_errors)
        super().__init__(message)


class GraphBuildError(OntoBridgeError):
    """Records break the ontology (type, properties or cardinality)."""

    def __init__(self, message: str, problems: list[str] | None = None) -> None:
        self.problems = problems or []
        if self.problems:
            message = message + "\n" + "\n".join(f"  - {p}" for p in self.problems)
        super().__init__(message)


class NodeNotFoundError(OntoBridgeError):
    """A node id does not exist in the graph store."""


class UnknownConceptError(OntoBridgeError):
    """A concept (entity) name is not part of the ontology."""


class UnknownMetricError(OntoBridgeError):
    """A metric name is not part of the ontology."""
