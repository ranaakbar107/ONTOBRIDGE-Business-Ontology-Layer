# ontobridge

[![CI](https://github.com/<your-github-username>/ontobridge/actions/workflows/ci.yml/badge.svg)](https://github.com/<your-github-username>/ontobridge/actions/workflows/ci.yml)
![Python 3.12](https://img.shields.io/badge/python-3.12-blue)
![License: MIT](https://img.shields.io/badge/license-MIT-green)

**A business ontology layer for AI agents.** Define your business in YAML, build an
in-memory knowledge graph from it, and let AI agents (Claude, Cursor, open-source
agents) query the *meaning* of your business over MCP.

```
Raw data  ->  Ontology as a semantic layer  ->  Agents connect over MCP
```

An agent asked *"what was revenue from buyers in Lahore?"* no longer guesses.
It learns that "buyer" means `Customer`, that revenue is
`sum of Order.amount where status = paid`, how `Customer` reaches `Order`, and it
can check whether the ontology covers the question at all before answering.

## Quickstart (5 steps)

```bash
# 1. Clone
git clone https://github.com/<your-github-username>/ontobridge.git && cd ontobridge
# 2. Create a virtual environment (Python 3.12+)
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
# 3. Install
pip install -e ".[dev]"
# 4. Check everything works
pytest
# 5. Run the e-commerce demo agent end to end
python examples/agent_demo.py
```

Start the MCP server yourself:

```bash
ontobridge --ontology examples/ecommerce/ontology.yaml \
           --mapping  examples/ecommerce/mapping.yaml             # stdio (for Claude Desktop, Cursor)

ontobridge --ontology examples/ecommerce/ontology.yaml \
           --mapping  examples/ecommerce/mapping.yaml \
           --transport http --port 8000                           # HTTP at http://127.0.0.1:8000/mcp
```

Paths can also be set with `ONTOBRIDGE_ONTOLOGY` and `ONTOBRIDGE_MAPPING`.

## Connect an MCP client

**Claude Desktop** - edit `claude_desktop_config.json`
(macOS: `~/Library/Application Support/Claude/`, Windows: `%APPDATA%\Claude\`):

```json
{
  "mcpServers": {
    "ontobridge": {
      "command": "/ABSOLUTE/PATH/ontobridge/.venv/bin/ontobridge",
      "args": [
        "--ontology", "/ABSOLUTE/PATH/ontobridge/examples/ecommerce/ontology.yaml",
        "--mapping",  "/ABSOLUTE/PATH/ontobridge/examples/ecommerce/mapping.yaml"
      ]
    }
  }
}
```

On Windows the command is `C:\\ABSOLUTE\\PATH\\ontobridge\\.venv\\Scripts\\ontobridge.exe`.
Restart Claude Desktop; the nine tools appear under the tools icon.

**Cursor** - put the same `mcpServers` block in `.cursor/mcp.json` in your project.

**Any MCP client over HTTP** - start with `--transport http` and point the client at
`http://127.0.0.1:8000/mcp`.

A ready-to-edit file is in [`examples/claude_desktop_config.json`](examples/claude_desktop_config.json).

## The nine MCP tools

All tools are read-only and every answer includes a `source` block.

| Tool | What it does |
|---|---|
| `list_concepts` | Lists all business concepts, relationships and metrics |
| `get_concept` | Properties, synonyms and relations of one concept |
| `search_terms` | Resolves a business word to a concept ("buyer" -> Customer) |
| `get_relationships` | Relations around a concept, with direction and cardinality |
| `find_path` | Shortest path between two concepts (Customer -places-> Order -contains-> Product) |
| `query_entities` | Filters instances of a concept (`{"status": "paid", "amount": {"gte": 100}}`) |
| `get_neighbors` | Instances connected to one node (the orders of `Customer:C001`) |
| `get_metric` | Definition, formula and computed value of a metric |
| `check_answerable` | Says if the ontology covers a question and names missing terms |

## Ontology as code

An ontology has four parts. The full reference is in
[`docs/ontology-format.md`](docs/ontology-format.md); the complete example is
[`examples/ecommerce/ontology.yaml`](examples/ecommerce/ontology.yaml).

```yaml
entities:                      # business concepts with typed properties and synonyms
  Customer:
    description: A person who buys products from the shop.
    synonyms: [client, buyer]
    properties:
      id: string
      name: string
      signup_date: date
  Order:
    properties:
      id: string
      amount: float
      status: string

relationships:                 # named, directed, with cardinality
  places: {from: Customer, to: Order, cardinality: one-to-many}

metrics:                       # business definitions an agent can resolve
  revenue:
    description: Total amount of paid orders
    synonyms: [sales]
    definition: {entity: Order, aggregate: sum, field: amount, filter: {status: paid}}
```

**Validated on load.** An unknown entity, a bad cardinality or a missing property
fails fast with a clear error that names the file and the problem:

```
Invalid ontology in ontology.yaml:
  - relationship 'places' refers to unknown entity 'Ordr' in 'to' (known entities: Customer)
```

Data is connected with a separate mapping file (CSV and JSON supported), so the
ontology stays about meaning. See [`examples/ecommerce/mapping.yaml`](examples/ecommerce/mapping.yaml).

## Architecture

```
Data sources (YAML ontology, CSV, JSON)
   -> 1. Input adapters      ontobridge.adapters   (registry: yaml, csv, json)
   -> 2. Ontology core       ontobridge.core       (Pydantic v2 models + validation)
   -> 3. Graph builder       ontobridge.builder    (typed nodes and edges, cardinality checks)
   -> 4. GraphStore          ontobridge.graph      (interface; in-memory NetworkX backend)
   -> 5. Semantic layer      ontobridge.semantic   (synonyms, metrics, paths, answerability)
   -> 6. MCP server          ontobridge.mcp_server (FastMCP, nine read-only tools)
   -> AI agents
```

**Build time** (once per ontology change): load YAML and data, validate, create nodes and
edges, index synonyms and metrics, graph ready in memory.
**Query time** (every question): the agent calls `search_terms`, `get_metric`,
`query_entities`... and the answer returns with its source.
Change the YAML, restart, and every agent sees the new meaning.

## Use it from Python

```python
from ontobridge import load_project

layer, report = load_project("examples/ecommerce/ontology.yaml", "examples/ecommerce/mapping.yaml")
layer.search_terms("buyer")  # -> Customer
layer.get_metric("revenue")["value"]  # -> 1926.5
layer.find_path("Customer", "Product")["text"]
layer.check_answerable("How much ad spend did we have?")["missing_terms"]  # ['ad', 'spend']
```

## Extending

* **New input format:** subclass `InputAdapter` and decorate it with
  `@register_adapter("name")`. No core code changes.
* **New graph backend (Neo4j, Kuzu, Omnigraph):** implement `GraphStore` and add it to
  `BACKENDS` in `tests/test_graphstore_contract.py`; it must pass the same contract tests.

## Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check .
pytest
```

## Scope of v0.1

In scope: ontology in YAML, Pydantic validation, CSV and JSON loaders, in-memory graph store,
synonyms, metrics and paths, read-only MCP server, e-commerce demo.
Out of scope for now: write/mutation operations on the graph, Neo4j and SQL connectors,
auto-generating ontologies from databases.

## License

MIT - see [LICENSE](LICENSE).
