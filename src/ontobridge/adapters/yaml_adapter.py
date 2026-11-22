"""Load an ontology YAML file into the Pydantic models and fail fast on errors."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from ontobridge.adapters.base import InputAdapter, register_adapter
from ontobridge.core.errors import OntologyValidationError
from ontobridge.core.models import Ontology


def _format_validation_error(exc: ValidationError) -> list[str]:
    messages: list[str] = []
    for err in exc.errors():
        location = ".".join(str(part) for part in err["loc"])
        msg = err["msg"].removeprefix("Value error, ")
        if err["type"] == "extra_forbidden":
            msg = "unknown field (check the spelling)"
        elif err["type"] == "enum":
            msg = f"{msg} (got {err.get('input')!r})"
        parts = [p for p in msg.split("; ") if p]
        for part in parts:
            messages.append(f"{location}: {part}" if location else part)
    return messages


def ontology_from_dict(data: Any, source: str = "<dict>") -> Ontology:
    """Validate a parsed mapping and return an Ontology, or raise OntologyValidationError."""
    if not isinstance(data, dict):
        raise OntologyValidationError(
            f"Invalid ontology in {source}: the top level must be a mapping with "
            f"'entities', 'relationships' and 'metrics'"
        )
    try:
        return Ontology.model_validate(data)
    except ValidationError as exc:
        errors = _format_validation_error(exc)
        message = f"Invalid ontology in {source}:\n" + "\n".join(f"  - {e}" for e in errors)
        raise OntologyValidationError(message, errors) from None


def ontology_from_yaml_string(text: str, source: str = "<string>") -> Ontology:
    try:
        data = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        raise OntologyValidationError(f"Invalid YAML in {source}: {exc}") from None
    return ontology_from_dict(data, source)


@register_adapter("yaml")
class YamlOntologyAdapter(InputAdapter):
    """Reads an ontology YAML file and returns a validated :class:`Ontology`."""

    extensions = (".yaml", ".yml")

    def load(self, source: str | Path, **options: Any) -> Ontology:
        path = Path(source)
        if not path.is_file():
            raise OntologyValidationError(f"Ontology file not found: {path}")
        return ontology_from_yaml_string(path.read_text(encoding="utf-8"), str(path))


def load_ontology(path: str | Path) -> Ontology:
    """Shortcut: ``load_ontology("ontology.yaml")``."""
    return YamlOntologyAdapter().load(path)
