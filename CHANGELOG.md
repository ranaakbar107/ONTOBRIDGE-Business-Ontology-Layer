# Changelog

## v0.1.0 - first release

- Ontology as code: entities, relationships, metrics and synonyms in YAML,
  validated on load with Pydantic v2 (fails fast with clear errors).
- Input adapter interface and registry with YAML, CSV and JSON adapters and a
  data mapping file; bad rows are reported with their row number.
- `GraphStore` interface with an in-memory NetworkX backend and a shared contract test suite.
- Graph builder that enforces types, required properties and cardinality.
- Semantic layer: synonym resolution, metric engine, concept paths, entity filters,
  neighbours and a question answerability checker.
- Read-only FastMCP server (stdio and HTTP) with nine tools.
- E-commerce demo (Customer, Order, Product, Category) and an end-to-end agent demo.
