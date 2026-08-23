from __future__ import annotations

import json
import logging
import os
import sys
from contextlib import AsyncExitStack
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.types import CallToolResult, TextContent

from n3rv.config import RuntimeSettings

logger = logging.getLogger("n3rv.mcp.client")


def _subprocess_env() -> dict[str, str]:
    """Build env for MCP server subprocess, propagating the current PYTHONPATH."""
    env = os.environ.copy()
    extra = os.pathsep.join(p for p in sys.path if p)
    existing = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = f"{extra}{os.pathsep}{existing}" if existing else extra
    return env


class MCPToolError(RuntimeError):
    pass


class StdioMCPClient:
    def __init__(self, *, settings: RuntimeSettings, module_name: str, runner_name: str) -> None:
        self.settings = settings
        self.module_name = module_name
        self.runner_name = runner_name

    async def call_tool(self, name: str, arguments: dict[str, Any] | None = None) -> Any:
        logger.debug("mcp call module=%s tool=%s", self.module_name, name)
        params = StdioServerParameters(
            command=sys.executable,
            args=[
                "-c",
                f"from {self.module_name} import {self.runner_name}; {self.runner_name}()",
            ],
            cwd=self.settings.paths.project_root,
            env=_subprocess_env(),
        )
        async with AsyncExitStack() as stack:
            read_stream, write_stream = await stack.enter_async_context(stdio_client(params))
            session = await stack.enter_async_context(ClientSession(read_stream, write_stream))
            await session.initialize()
            result = await session.call_tool(name, arguments or {})
            if result.isError:
                err = self._extract_error(result)
                logger.error("mcp tool error module=%s tool=%s: %s", self.module_name, name, err)
                raise MCPToolError(err)
            logger.debug("mcp call ok module=%s tool=%s", self.module_name, name)
            return self._decode_result(result)

    def _decode_result(self, result: CallToolResult) -> Any:
        if result.structuredContent is not None:
            return result.structuredContent

        if len(result.content) == 1 and isinstance(result.content[0], TextContent):
            text = result.content[0].text
            try:
                return json.loads(text)
            except json.JSONDecodeError:
                return text

        decoded: list[Any] = []
        for item in result.content:
            if isinstance(item, TextContent):
                try:
                    decoded.append(json.loads(item.text))
                except json.JSONDecodeError:
                    decoded.append(item.text)
            else:
                decoded.append(item.model_dump(mode="json"))
        return decoded

    def _extract_error(self, result: CallToolResult) -> str:
        payload = self._decode_result(result)
        if isinstance(payload, dict) and "error" in payload:
            return str(payload["error"])
        return str(payload)


class HubMCPBridge:
    def __init__(self, settings: RuntimeSettings) -> None:
        self.memory = StdioMCPClient(
            settings=settings,
            module_name="n3rv.mcp.memory_server",
            runner_name="run_memory_server",
        )

    async def start(self) -> None:
        return None

    async def close(self) -> None:
        return None

    async def memory_search(self, *, query: str, limit: int = 5, type_filter: str | None = None) -> dict:
        result = await self.memory.call_tool(
            "memory_search",
            {"query": query, "limit": limit, "type_filter": type_filter},
        )
        if isinstance(result, dict) and "result" in result:
            return result["result"]
        return result

    async def memory_save(
        self,
        *,
        content: str,
        title: str,
        type: str,
        topic_key: str | None = None,
        scope: str = "project",
    ) -> dict:
        return await self.memory.call_tool(
            "memory_save",
            {
                "content": content,
                "title": title,
                "type": type,
                "topic_key": topic_key,
                "scope": scope,
            },
        )
