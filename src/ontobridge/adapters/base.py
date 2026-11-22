"""The common interface every input adapter implements, plus a registry by format name.

Adding a new format never touches core code::

    from ontobridge.adapters import InputAdapter, register_adapter

    @register_adapter("parquet")
    class ParquetAdapter(InputAdapter):
        def load(self, source, **options):
            ...
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

from ontobridge.core.errors import AdapterNotFoundError


class InputAdapter(ABC):
    """Reads one source format and returns ontobridge's internal model.

    * ontology adapters (``yaml``) return an :class:`~ontobridge.core.models.Ontology`
    * data adapters (``csv``, ``json``) return a :class:`~ontobridge.core.records.RawTable`
    """

    #: Name the adapter is registered under, e.g. "csv". Set by ``register_adapter``.
    name: ClassVar[str] = ""
    #: File extensions this adapter handles, used to infer the format from a path.
    extensions: ClassVar[tuple[str, ...]] = ()

    @abstractmethod
    def load(self, source: str | Path, **options: Any) -> Any:
        """Load ``source`` and return the internal model."""


_REGISTRY: dict[str, type[InputAdapter]] = {}


def register_adapter(name: str) -> Callable[[type[InputAdapter]], type[InputAdapter]]:
    """Class decorator that registers an adapter under ``name``."""

    def decorator(cls: type[InputAdapter]) -> type[InputAdapter]:
        if not (isinstance(cls, type) and issubclass(cls, InputAdapter)):
            raise TypeError(f"{cls!r} must subclass InputAdapter")
        cls.name = name.lower()
        _REGISTRY[cls.name] = cls
        return cls

    return decorator


def unregister_adapter(name: str) -> None:
    _REGISTRY.pop(name.lower(), None)


def get_adapter(name: str) -> InputAdapter:
    """Return a new instance of the adapter registered as ``name`` (case-insensitive)."""
    cls = _REGISTRY.get(name.lower())
    if cls is None:
        raise AdapterNotFoundError(
            f"No input adapter registered for '{name}'. "
            f"Available: {', '.join(sorted(_REGISTRY)) or 'none'}"
        )
    return cls()


def adapter_for_path(path: str | Path) -> InputAdapter:
    """Pick an adapter from a file extension, e.g. ``orders.csv`` -> csv adapter."""
    suffix = Path(path).suffix.lower()
    for cls in _REGISTRY.values():
        if suffix in cls.extensions:
            return cls()
    raise AdapterNotFoundError(f"No input adapter handles '{suffix}' files ({path})")


def available_adapters() -> list[str]:
    return sorted(_REGISTRY)
