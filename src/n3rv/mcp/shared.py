from __future__ import annotations

import os
from pathlib import Path
from typing import Any
from uuid import uuid4

import httpx
from mcp.server.fastmcp import FastMCP
from pydantic import BaseModel

from n3rv.config import RuntimePaths, RuntimeSettings, load_runtime_settings


def ensure_runtime_directories(paths: RuntimePaths) -> None:
    for directory in (
        paths.memory_dir,
        paths.n3rv_dir,
        paths.hub_state_dir,
        paths.logs_dir,
    ):
        directory.mkdir(parents=True, exist_ok=True)


def resolve_runtime_settings(project_root: Path | None = None) -> RuntimeSettings:
    settings = load_runtime_settings(project_root)
    ensure_runtime_directories(settings.paths)
    return settings


def detect_agent_source() -> str:
    return os.environ.get("N3RV_AGENT_SOURCE", "opencode")


def result_payload(
    value: BaseModel | list[BaseModel] | dict[str, Any] | list[dict[str, Any]],
) -> Any:
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, list):
        return [item.model_dump(mode="json") if isinstance(item, BaseModel) else item for item in value]
    return value


def hub_rpc(hub_url: str, method: str, params: dict) -> dict:
    """Make a JSON-RPC call to the hub and return the result dict."""
    try:
        resp = httpx.post(
            f"{hub_url}/rpc",
            json={
                "jsonrpc": "2.0",
                "id": f"hub-mcp-{uuid4().hex[:8]}",
                "method": method,
                "params": params,
            },
            timeout=10.0,
        )
        resp.raise_for_status()
    except httpx.HTTPError as exc:
        raise Exception(f"HubUnavailable: {exc}") from exc
    data = resp.json()
    if "error" in data:
        raise Exception(f"HubError: {data['error'].get('message', data['error'])}")
    return data["result"]


def build_mcp_server(name: str, instructions: str) -> FastMCP:
    return FastMCP(
        name=name,
        instructions=instructions,
        dependencies=(),
        debug=False,
        log_level="INFO",
        stateless_http=True,
        json_response=True,
    )
