"""End-to-end demo: an agent connects to the ontobridge MCP server and answers questions.

It starts the real server as a subprocess over stdio (exactly like Claude Desktop or
Cursor would), lists the tools, then answers three business questions using only
MCP tool calls. Every step is printed and written to a Markdown log for review.

    python examples/agent_demo.py                 # print to the terminal
    python examples/agent_demo.py --log run.md    # also save a log
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from fastmcp import Client

HERE = Path(__file__).resolve().parent
ONTOLOGY = HERE / "ecommerce" / "ontology.yaml"
MAPPING = HERE / "ecommerce" / "mapping.yaml"


class Log:
    def __init__(self) -> None:
        self.lines: list[str] = []

    def __call__(self, text: str = "") -> None:
        print(text)
        self.lines.append(text)

    def save(self, path: Path) -> None:
        path.write_text("\n".join(self.lines) + "\n", encoding="utf-8")


async def call(client: Client, log: Log, tool: str, **args: Any) -> dict[str, Any]:
    result = await client.call_tool(tool, args)
    data = result.structured_content or json.loads(result.content[0].text)
    log(f"- `{tool}({json.dumps(args)})`")
    return data


async def run(log: Log) -> None:
    config = {
        "mcpServers": {
            "ontobridge": {
                "command": sys.executable,
                "args": [
                    "-m",
                    "ontobridge.mcp_server.server",
                    "--ontology",
                    str(ONTOLOGY),
                    "--mapping",
                    str(MAPPING),
                ],
            }
        }
    }
    async with Client(config) as client:
        tools = await client.list_tools()
        log("# ontobridge agent demo")
        log()
        log(
            f"Connected over stdio. The server exposes {len(tools)} tools: "
            + ", ".join(sorted(t.name for t in tools))
        )

        # Q1 -----------------------------------------------------------------------
        log()
        log("## Q1: What does revenue mean?")
        check = await call(client, log, "check_answerable", question="What does revenue mean?")
        log(f"  answerable={check['answerable']} coverage={check['coverage']}")
        term = await call(client, log, "search_terms", term="revenue")
        metric_name = term["matches"][0]["target"]
        metric = await call(client, log, "get_metric", name=metric_name)
        log()
        log(
            f"**Answer:** {metric['description']} Formula: `{metric['formula']}`. "
            f"Current value: {metric['value']} (from {metric['records_used']} orders). "
            f"Source: {metric['source']['ontology_file']}."
        )

        # Q2 -----------------------------------------------------------------------
        log()
        log("## Q2: Which orders did Ali place?")
        check = await call(client, log, "check_answerable", question="Which orders did Ali place?")
        log(f"  answerable={check['answerable']} coverage={check['coverage']}")
        path = await call(client, log, "find_path", from_concept="Customer", to_concept="Order")
        log(f"  path: {path['text']}")
        customers = await call(
            client,
            log,
            "query_entities",
            concept="Customer",
            filters={"name": {"contains": "Ali"}},
            limit=5,
        )
        ali = customers["results"][0]
        orders = await call(
            client,
            log,
            "get_neighbors",
            node_id=ali["id"],
            relationship="places",
            direction="out",
            limit=50,
        )
        order_ids = [n["id"] for n in orders["neighbors"]]
        log()
        lines = [
            f"{n['id']} ({n['properties']['order_date']}, {n['properties']['amount']} USD, "
            f"{n['properties']['status']})"
            for n in orders["neighbors"]
        ]
        log(
            f"**Answer:** {ali['properties']['name']} ({ali['id']}) placed "
            f"{orders['count']} orders: " + "; ".join(lines) + "."
        )

        # Q3 -----------------------------------------------------------------------
        log()
        log("## Q3: Which products are in them?")
        products: dict[str, str] = {}
        for order_id in order_ids:
            items = await call(
                client,
                log,
                "get_neighbors",
                node_id=order_id,
                relationship="contains",
                direction="out",
                limit=50,
            )
            for n in items["neighbors"]:
                products[n["id"]] = n["properties"]["name"]
        log()
        log(
            "**Answer:** "
            + ", ".join(f"{name} ({pid})" for pid, name in sorted(products.items()))
            + "."
        )

        # Guardrail ----------------------------------------------------------------
        log()
        log("## Guardrail: How much ad spend did we have last month?")
        check = await call(
            client, log, "check_answerable", question="How much ad spend did we have last month?"
        )
        log()
        log(f"**Answer:** I can't answer this from the business ontology: {check['reason']}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--log", type=Path, help="Write a Markdown log of the run here")
    args = parser.parse_args()
    log = Log()
    asyncio.run(run(log))
    if args.log:
        log.save(args.log)
        print(f"\nLog written to {args.log}", file=sys.stderr)


if __name__ == "__main__":
    main()
