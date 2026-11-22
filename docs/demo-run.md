# ontobridge agent demo

Connected over stdio. The server exposes 9 tools: check_answerable, find_path, get_concept, get_metric, get_neighbors, get_relationships, list_concepts, query_entities, search_terms

## Q1: What does revenue mean?
- `check_answerable({"question": "What does revenue mean?"})`
  answerable=True coverage=1.0
- `search_terms({"term": "revenue"})`
- `get_metric({"name": "revenue"})`

**Answer:** Total amount of paid orders. Pending, refunded and cancelled orders do not count. Formula: `sum of Order.amount where status = paid`. Current value: 1926.5 (from 20 orders). Source: ontology.yaml.

## Q2: Which orders did Ali place?
- `check_answerable({"question": "Which orders did Ali place?"})`
  answerable=True coverage=1.0
- `find_path({"from_concept": "Customer", "to_concept": "Order"})`
  path: Customer -places-> Order
- `query_entities({"concept": "Customer", "filters": {"name": {"contains": "Ali"}}, "limit": 5})`
- `get_neighbors({"node_id": "Customer:C001", "relationship": "places", "direction": "out", "limit": 50})`

**Answer:** Ali Khan (Customer:C001) placed 4 orders: Order:O001 (2026-01-03, 118.0 USD, pending); Order:O008 (2026-03-07, 159.0 USD, paid); Order:O016 (2026-05-18, 79.5 USD, pending); Order:O023 (2026-07-20, 108.0 USD, paid).

## Q3: Which products are in them?
- `get_neighbors({"node_id": "Order:O001", "relationship": "contains", "direction": "out", "limit": 50})`
- `get_neighbors({"node_id": "Order:O008", "relationship": "contains", "direction": "out", "limit": 50})`
- `get_neighbors({"node_id": "Order:O016", "relationship": "contains", "direction": "out", "limit": 50})`
- `get_neighbors({"node_id": "Order:O023", "relationship": "contains", "direction": "out", "limit": 50})`

**Answer:** Wireless Mouse (Product:P001), Mechanical Keyboard (Product:P002), USB-C Charger (Product:P003), Python Crash Course (Product:P005), Designing Data-Intensive Applications (Product:P007), Chef Knife (Product:P008), Non-stick Pan (Product:P010), Yoga Mat (Product:P011).

## Guardrail: How much ad spend did we have last month?
- `check_answerable({"question": "How much ad spend did we have last month?"})`

**Answer:** I can't answer this from the business ontology: The ontology does not define: ad, spend. Add them as entities, properties, metrics or synonyms.
