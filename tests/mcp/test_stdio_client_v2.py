from __future__ import annotations

import pytest

from n3rv.mcp.client import StdioMCPClient


@pytest.mark.asyncio
async def test_stdio_roundtrip_memory_save_and_search(runtime_settings) -> None:
    client = StdioMCPClient(
        settings=runtime_settings,
        module_name="n3rv.mcp.memory_server",
        runner_name="run_memory_server",
    )
    saved = await client.call_tool(
        "memory_save",
        {"content": "v2 smoke hello", "title": "v2 smoke", "type": "note", "topic_key": "v2-smoke", "scope": "project"},
    )
    assert saved["topic_key"] == "v2-smoke"
    assert saved["status"] in {"created", "updated"}

    search = await client.call_tool("memory_search", {"query": "smoke hello", "limit": 2})
    assert "results" in search
    assert any(r["topic_key"] == "v2-smoke" for r in search["results"])

    recalled = await client.call_tool("memory_recall", {"topic_key": "v2-smoke"})
    assert recalled["found"] is True
    assert recalled["content"] == "v2 smoke hello"


@pytest.mark.asyncio
async def test_build_mcp_server_import(runtime_settings) -> None:
    from n3rv.mcp.shared import build_mcp_server

    server = build_mcp_server("test-server", "test instructions")
    assert server.name == "test-server"

    # verify tool registration works on v2 server
    @server.tool()
    def dummy(x: str) -> str:
        """dummy"""
        return x

    tools = await server.list_tools()
    assert any(t.name == "dummy" for t in tools)
