# Ontology format reference

An ontology is one YAML file with four parts: **entities**, **relationships**,
**metrics** and **synonyms** (synonyms live inside the other three).

```yaml
name: ecommerce          # optional
version: "1.0"           # optional
description: ...         # optional
entities: {...}
relationships: {...}
metrics: {...}
```

## Entities

Business concepts with typed properties.

```yaml
entities:
  Customer:
    description: A person who buys products.   # optional
    key: id                                    # optional, default "id"; must be a property
    synonyms: [client, buyer]                  # optional
    properties:
      id: string                               # short form
      city: {type: string, required: false, description: City}   # long form
```

Property types: `string`, `integer`, `float`, `boolean`, `date` (`2026-01-31`),
`datetime` (`2026-01-31T10:00:00`). Properties are `required: true` by default.

## Relationships

Named and directed, with a cardinality.

```yaml
relationships:
  places:
    from: Customer
    to: Order
    cardinality: one-to-many     # one-to-one | one-to-many | many-to-one | many-to-many
    description: ...             # optional
    synonyms: [ordered]          # optional
```

Cardinality is enforced when the graph is built: with `one-to-many` an `Order` can
have only one `Customer`.

## Metrics

Business definitions an agent can resolve.

```yaml
metrics:
  revenue:
    description: Total amount of paid orders.
    synonyms: [sales]
    definition:
      entity: Order
      aggregate: sum            # sum | count | avg | min | max
      field: amount             # required unless aggregate is count
      filter: {status: paid}    # optional
```

Filters use equality (`{status: paid}`) or operators:
`{amount: {gte: 100}}`, `{status: {in: [paid, pending]}}`, `{name: {contains: ali}}`.
Operators: `eq`, `ne`, `gt`, `gte`, `lt`, `lte`, `in`, `contains`.

## Synonyms

Every entity, relationship and metric can list `synonyms`. Matching ignores case,
punctuation, `snake_case` / `CamelCase` and simple plurals, so `Buyers`, `buyer` and
`BUYER` all resolve to `Customer`. A word can only mean one thing: using the same
synonym for two concepts is a validation error.

## Validation (fails fast)

Loading stops with an `OntologyValidationError` that lists every problem, e.g.:

* a relationship or metric refers to an unknown entity
* a cardinality or property type is not allowed
* a metric uses or filters on a property the entity does not have
* `sum`/`avg` on a non-numeric property
* an entity key that is not a property
* a misspelled field (`propertes:`)
* the same synonym used for two concepts

## Data mapping

Data is mapped in a separate file so the ontology stays about meaning.

```yaml
data_dir: data                       # relative to this file
entities:
  Customer: {source: customers.csv}
  Order:    {source: orders.csv, columns: {order_id: id}}   # file column -> property
  Category: {source: categories.json, path: categories}     # JSON list under a key
relationships:
  places:   {source: orders.csv, from: customer_id, to: order_id}
```

For a relationship, `from` is the column holding the key of the `from` entity and `to`
the column holding the key of the `to` entity. A blank cell means "no link".
Any other bad row (wrong type, missing required value, duplicate key) is reported with
its file and row number and loading stops: no row is dropped silently.
