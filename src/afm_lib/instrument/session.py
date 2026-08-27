from __future__ import annotations

import json
from typing import Any

from langchain_mcp_adapters.client import MultiServerMCPClient

from afm_lib.config import SPM_MCP_SERVER_CONFIG

_client: MultiServerMCPClient | None = None
_registry: dict[str, Any] | None = None


class InstrumentError(RuntimeError):
    """The instrument refused or failed a command (ok=False)."""


async def _get_tool(name: str):
    """Process-wide client: the tool registry is fetched once per session."""
    global _client, _registry
    if _client is None:
        _client = MultiServerMCPClient(SPM_MCP_SERVER_CONFIG)
    if _registry is None:
        _registry = {t.name: t for t in await _client.get_tools()}
    if name not in _registry:
        raise ValueError(f"Tool {name!r} not on the MCP server. "
                         f"Available: {sorted(_registry)}")
    return _registry[name]


def unwrap(result: Any, tool: str) -> dict:
    """ToolOutcome envelope -> data dict. Raises loudly on ok=False."""
    if isinstance(result, (list, tuple)):
        result = result[0]
    if isinstance(result, dict) and "text" in result:
        result = json.loads(result["text"])
    elif isinstance(result, str):
        result = json.loads(result)

    if not result.get("ok"):
        err = result.get("error", {}) or {}
        raise InstrumentError(
            f"{tool}: {err.get('code', 'unknown')}: {err.get('message', result)}")
    return result.get("data", {})


async def call(tool: str, args: dict | None = None) -> dict:
    """Call an SPM MCP tool and return its `data` payload."""
    t = await _get_tool(tool)
    return unwrap(await t.ainvoke(args or {}), tool)