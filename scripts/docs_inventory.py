#!/usr/bin/env python3
"""Report a lightweight inventory for active documentation reviews."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]


ENDPOINT_PATTERN = re.compile(r"@router\.(get|post|put|patch|delete)\(")
WEBSOCKET_PATTERN = re.compile(r"@router\.websocket\(")
HOOK_PATTERN = re.compile(r"export function (use[A-Za-z0-9_]+)\(")


@dataclass
class RouteInventory:
    file: str
    http_endpoints: int
    websocket_endpoints: int


def iter_files(paths: Iterable[Path]) -> list[str]:
    return [str(path.relative_to(ROOT)) for path in sorted(paths)]


def route_inventory() -> list[RouteInventory]:
    files = []
    for path in sorted((ROOT / "devgodzilla/api/routes").glob("*.py")):
        text = path.read_text()
        http_endpoints = len(ENDPOINT_PATTERN.findall(text))
        websocket_endpoints = len(WEBSOCKET_PATTERN.findall(text))
        if http_endpoints == 0 and websocket_endpoints == 0:
            continue
        files.append(
            RouteInventory(
                file=str(path.relative_to(ROOT)),
                http_endpoints=http_endpoints,
                websocket_endpoints=websocket_endpoints,
            )
        )
    return files


def hook_inventory() -> dict[str, list[str]]:
    result: dict[str, list[str]] = {}
    for path in sorted((ROOT / "frontend/lib/api/hooks").glob("*.ts")):
        hooks = HOOK_PATTERN.findall(path.read_text())
        result[str(path.relative_to(ROOT))] = hooks
    return result


def build_inventory() -> dict[str, object]:
    routes = route_inventory()
    hooks = hook_inventory()
    return {
        "routes": {
            "files": [asdict(item) for item in routes],
            "totals": {
                "route_files": len(routes),
                "http_endpoints": sum(item.http_endpoints for item in routes),
                "websocket_endpoints": sum(item.websocket_endpoints for item in routes),
            },
        },
        "services": [
            item
            for item in iter_files((ROOT / "devgodzilla/services").glob("*.py"))
            if not item.endswith("/__init__.py")
        ],
        "frontend_pages": iter_files((ROOT / "frontend/app").rglob("page.tsx")),
        "frontend_hooks": {
            "files": hooks,
            "totals": {
                "hook_files": len(hooks),
                "exported_hooks": sum(len(items) for items in hooks.values()),
            },
        },
        "windmill": {
            "flows": iter_files((ROOT / "windmill/flows/devgodzilla").glob("*.json")),
            "scripts": iter_files((ROOT / "windmill/scripts/devgodzilla").glob("*.py")),
        },
    }


def print_markdown(inventory: dict[str, object]) -> None:
    routes = inventory["routes"]  # type: ignore[index]
    hooks = inventory["frontend_hooks"]  # type: ignore[index]
    windmill = inventory["windmill"]  # type: ignore[index]
    print("# Docs Inventory")
    print()
    print("| Surface | Count |")
    print("|---|---:|")
    print(f"| API route files | {routes['totals']['route_files']} |")
    print(f"| HTTP endpoints | {routes['totals']['http_endpoints']} |")
    print(f"| WebSocket endpoints | {routes['totals']['websocket_endpoints']} |")
    print(f"| Service modules | {len(inventory['services'])} |")
    print(f"| Frontend pages | {len(inventory['frontend_pages'])} |")
    print(f"| Frontend hook files | {hooks['totals']['hook_files']} |")
    print(f"| Exported frontend hooks | {hooks['totals']['exported_hooks']} |")
    print(f"| Windmill flows | {len(windmill['flows'])} |")
    print(f"| Windmill scripts | {len(windmill['scripts'])} |")
    print()
    print("## API Routes")
    for item in routes["files"]:
        print(
            f"- `{item['file']}`: http={item['http_endpoints']} ws={item['websocket_endpoints']}"
        )
    print()
    print("## Services")
    for item in inventory["services"]:
        print(f"- `{item}`")
    print()
    print("## Frontend Pages")
    for item in inventory["frontend_pages"]:
        print(f"- `{item}`")
    print()
    print("## Frontend Hooks")
    for file_name, exported in hooks["files"].items():
        label = ", ".join(f"`{name}`" for name in exported) if exported else "none"
        print(f"- `{file_name}`: {label}")
    print()
    print("## Windmill Flows")
    for item in windmill["flows"]:
        print(f"- `{item}`")
    print()
    print("## Windmill Scripts")
    for item in windmill["scripts"]:
        print(f"- `{item}`")


def main() -> None:
    inventory = build_inventory()
    if "--json" in __import__("sys").argv:
        print(json.dumps(inventory, indent=2))
        return
    print_markdown(inventory)


if __name__ == "__main__":
    main()
