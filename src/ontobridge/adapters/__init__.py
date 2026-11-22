"""Input adapters: convert YAML, CSV and JSON into ontobridge's internal model.

Importing this package registers the built-in adapters (yaml, csv, json).
"""

from ontobridge.adapters.base import (
    InputAdapter,
    adapter_for_path,
    available_adapters,
    get_adapter,
    register_adapter,
    unregister_adapter,
)
from ontobridge.adapters.csv_adapter import CsvAdapter
from ontobridge.adapters.json_adapter import JsonAdapter
from ontobridge.adapters.mapping import DataMapping, load_dataset, load_mapping
from ontobridge.adapters.yaml_adapter import (
    YamlOntologyAdapter,
    load_ontology,
    ontology_from_dict,
    ontology_from_yaml_string,
)

__all__ = [
    "CsvAdapter",
    "DataMapping",
    "InputAdapter",
    "JsonAdapter",
    "YamlOntologyAdapter",
    "adapter_for_path",
    "available_adapters",
    "get_adapter",
    "load_dataset",
    "load_mapping",
    "load_ontology",
    "ontology_from_dict",
    "ontology_from_yaml_string",
    "register_adapter",
    "unregister_adapter",
]
