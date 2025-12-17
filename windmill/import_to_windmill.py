#!/usr/bin/env python3
"""
Windmill Script Importer

Imports DevGodzilla scripts and flows to Windmill via the API.

Usage:
    python import_to_windmill.py --url http://192.168.1.227 --token <TOKEN>
    
To get a token:
1. Go to Windmill UI > Settings > Tokens
2. Create a new token with admin permissions
"""

import argparse
import json
import os
import sys
from pathlib import Path
import urllib.request
import urllib.error
import re

SCRIPTS_DIR = Path(__file__).parent / "scripts" / "devgodzilla"
FLOWS_DIR = Path(__file__).parent / "flows" / "devgodzilla"
APPS_DIR = Path(__file__).parent / "apps" / "devgodzilla"


def read_script_content(script_path: Path) -> str:
    """Read Python script content."""
    return script_path.read_text()


def create_script_payload(path: str, content: str, summary: str = "") -> dict:
    """Create Windmill script API payload."""
    return {
        "path": path,
        "summary": summary,
        "description": f"DevGodzilla script: {path}",
        "content": content,
        "language": "python3",
        "is_template": False,
        "kind": "script",
        "tag": "devgodzilla",
    }


def api_request(base_url: str, endpoint: str, token: str, method: str = "GET", data: dict = None) -> dict:
    """Make API request to Windmill."""
    url = f"{base_url}/api{endpoint}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    
    req_data = json.dumps(data).encode() if data else None
    req = urllib.request.Request(url, data=req_data, headers=headers, method=method)
    
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode()
            try:
                return json.loads(body) if body else {}
            except json.JSONDecodeError:
                return {"version": body.strip()}  # Handle plain text response
    except urllib.error.HTTPError as e:
        error_body = e.read().decode() if e.fp else str(e)
        print(f"  Error: {e.code} - {error_body[:100]}")
        return {"error": error_body, "code": e.code}
    except Exception as e:
        return {"error": str(e)}

def _load_token_from_env_file(path: Path) -> str | None:
    """
    Load a token from a simple KEY=VALUE env file.

    Recognized keys (first match wins):
    - WINDMILL_TOKEN
    - DEVGODZILLA_WINDMILL_TOKEN
    - VITE_TOKEN (Windmill React app dev token)
    """
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    keys = ["WINDMILL_TOKEN", "DEVGODZILLA_WINDMILL_TOKEN", "VITE_TOKEN"]
    for key in keys:
        m = re.search(rf"^{re.escape(key)}=(.*)$", text, flags=re.MULTILINE)
        if not m:
            continue
        value = m.group(1).strip()
        if value and not value.startswith("your_"):
            return value
    return None


def create_script(base_url: str, token: str, workspace: str, path: str, content: str, summary: str) -> bool:
    """Create or update a script in Windmill."""
    
    # Check if script exists
    check = api_request(base_url, f"/w/{workspace}/scripts/get/p/{path}", token)
    
    exists = "error" not in check

    payload = {
        "path": path,
        "summary": summary,
        "description": f"DevGodzilla: {summary}",
        "content": content,
        "language": "python3",
        "is_template": False,
    }

    if exists:
        # Script exists: create a new version by chaining from the latest hash.
        # Without parent_hash, Windmill rejects the create with a path-conflict.
        print("  Script exists, creating new version...")
        existing_hash = check.get("hash")
        if existing_hash:
            payload["parent_hash"] = existing_hash

    result = api_request(base_url, f"/w/{workspace}/scripts/create", token, "POST", payload)

    # If still conflicting, archive then create (last resort).
    if "error" in result and result.get("code") == 400 and "Path conflict" in str(result.get("error", "")):
        api_request(base_url, f"/w/{workspace}/scripts/archive/p/{path}", token, "POST", {})
        result = api_request(base_url, f"/w/{workspace}/scripts/create", token, "POST", payload)
    
    return "error" not in result


def create_flow(base_url: str, token: str, workspace: str, path: str, flow_def: dict) -> bool:
    """Create or update a flow in Windmill."""
    
    # Check if flow exists
    check = api_request(base_url, f"/w/{workspace}/flows/get/{path}", token)
    
    payload = {
        "path": path,
        "summary": flow_def.get("summary", ""),
        "description": flow_def.get("description", ""),
        "value": flow_def.get("value", {}),
        "schema": flow_def.get("schema", {}),
    }
    
    if "error" not in check or check.get("code") != 404:
        # Flow exists, update it
        print(f"  Flow exists, updating...")
        result = api_request(base_url, f"/w/{workspace}/flows/update/{path}", token, "POST", payload)
    else:
        # Create new flow
        result = api_request(base_url, f"/w/{workspace}/flows/create", token, "POST", payload)
    
    return "error" not in result


def _inject_script_hashes_into_flow(base_url: str, token: str, workspace: str, flow_def: dict) -> None:
    """
    Best-effort: add script hashes to PathScript modules.

    Some Windmill deployments disallow running scripts by path via the jobs API.
    Including the script hash allows flows to execute script modules reliably.
    """

    def visit(node: object) -> None:
        if isinstance(node, dict):
            # PathScript node (OpenFlow schema)
            if node.get("type") == "script" and node.get("path") and not node.get("hash"):
                path = node["path"]
                info = api_request(base_url, f"/w/{workspace}/scripts/get/p/{path}", token)
                if "hash" in info:
                    node["hash"] = info["hash"]

            # Windmill flow module wrapper commonly stores the spec under "value"
            inner = node.get("value")
            if isinstance(inner, (dict, list)):
                visit(inner)

            # Recurse into all child containers (modules, branches, etc.)
            for v in node.values():
                if isinstance(v, (dict, list)):
                    visit(v)

        elif isinstance(node, list):
            for item in node:
                visit(item)

    visit(flow_def.get("value", {}))
def create_app(base_url: str, token: str, workspace: str, path: str, app_def: dict) -> bool:
    """Create or update an app in Windmill."""
    
    # Check if app exists
    check = api_request(base_url, f"/w/{workspace}/apps/get/{path}", token)
    
    payload = {
        "path": path,
        "summary": app_def.get("summary", ""),
        "value": app_def.get("value", {}),
        "policy": app_def.get("policy", {"execution_mode": "viewer"}),
    }
    
    if "error" not in check or check.get("code") != 404:
        # App exists, update it
        print(f"  App exists, updating...")
        result = api_request(base_url, f"/w/{workspace}/apps/update/{path}", token, "POST", payload)
    else:
        # Create new app
        result = api_request(base_url, f"/w/{workspace}/apps/create", token, "POST", payload)
        
        # Fallback: if create fails with 400, it might exist but hidden/archived or check failed
        if "error" in result and result.get("code") == 400:
             print(f"  Create failed (400), trying update...", end=" ")
             result = api_request(base_url, f"/w/{workspace}/apps/update/{path}", token, "POST", payload)
    
    return "error" not in result

def main():
    parser = argparse.ArgumentParser(description="Import DevGodzilla to Windmill")
    parser.add_argument("--url", default="http://192.168.1.227", help="Windmill base URL")
    parser.add_argument("--token", required=False, help="Windmill API token (or set WINDMILL_TOKEN env var)")
    parser.add_argument(
        "--token-file",
        required=False,
        help="Path to an env file containing WINDMILL_TOKEN/DEVGODZILLA_WINDMILL_TOKEN/VITE_TOKEN",
    )
    parser.add_argument("--workspace", default="demo1", help="Windmill workspace")
    parser.add_argument("--scripts-only", action="store_true", help="Only import scripts")
    parser.add_argument("--flows-only", action="store_true", help="Only import flows")
    args = parser.parse_args()

    token = args.token
    if not token and args.token_file:
        token = _load_token_from_env_file(Path(args.token_file))
    if not token:
        token = os.environ.get("WINDMILL_TOKEN") or os.environ.get("DEVGODZILLA_WINDMILL_TOKEN")
    if not token:
        print("Error: missing token (pass --token, or set WINDMILL_TOKEN, or use --token-file)")
        sys.exit(2)
    
    print(f"Importing DevGodzilla to {args.url} (workspace: {args.workspace})")
    print()
    
    # Test connection
    version = api_request(args.url, "/version", token)
    if "error" in version:
        print(f"Error connecting to Windmill: {version['error']}")
        sys.exit(1)
    print(f"Connected to Windmill {version}")
    print()
    
    success_count = 0
    error_count = 0
    
    # Import scripts
    if not args.flows_only:
        print("=== Importing Scripts ===")

        script_files = sorted([p for p in SCRIPTS_DIR.glob("*.py") if p.is_file()])
        for script_file in script_files:
            script_name = script_file.stem
            path = f"u/devgodzilla/{script_name}"
            summary = script_name.replace("_", " ").strip().title()

            content = read_script_content(script_file)
            print(f"Importing {path}...", end=" ")

            if create_script(args.url, token, args.workspace, path, content, summary):
                print("✓")
                success_count += 1
            else:
                print("✗")
                error_count += 1
        print()
    
    # Import flows
    if not args.scripts_only:
        print("=== Importing Flows ===")

        flow_files = sorted([p for p in FLOWS_DIR.glob("*.flow.json") if p.is_file()])
        for flow_file in flow_files:
            flow_name = flow_file.name.removesuffix(".flow.json")
            path = f"f/devgodzilla/{flow_name}"
            flow_def = json.loads(flow_file.read_text())
            _inject_script_hashes_into_flow(args.url, token, args.workspace, flow_def)
            print(f"Importing {path}...", end=" ")

            if create_flow(args.url, token, args.workspace, path, flow_def):
                print("✓")
                success_count += 1
            else:
                print("✗")
                error_count += 1
        print()
    
    # Import apps
    if not args.scripts_only and not args.flows_only:
        print("=== Importing Apps ===")
        apps = [
            ("devgodzilla_dashboard", "app/devgodzilla/dashboard"),
            ("devgodzilla_projects", "app/devgodzilla/projects"),
            ("devgodzilla_project_detail", "app/devgodzilla/project_detail"),
            ("devgodzilla_protocols", "app/devgodzilla/protocols"),
            ("devgodzilla_protocol_detail", "app/devgodzilla/protocol_detail"),
        ]
        
        for app_name, path in apps:
            app_file = APPS_DIR / f"{app_name}.app.json"
            
            if not app_file.exists():
                print(f"✗ {path} - file not found ({app_file})")
                error_count += 1
                continue
                
            app_def = json.loads(app_file.read_text())
            print(f"Importing {path}...", end=" ")
            
            if create_app(args.url, token, args.workspace, path, app_def):
                print("✓")
                success_count += 1
            else:
                print("✗")
                error_count += 1
        print()
    
    print(f"=== Summary ===")
    print(f"Success: {success_count}")
    print(f"Errors: {error_count}")
    
    return 0 if error_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
