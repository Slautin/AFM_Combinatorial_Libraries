# src/spm_agent/mcp/scifireaders_service.py

import json
import subprocess
from typing import Any

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from afm_lib.config import SCIFIREADERS_MCP_COMMAND


class SciFiReadersService:
    """
    Small client wrapper around the SciFiReaders MCP server.

    The service hides MCP-specific result objects and always tries to return
    a normal Python dictionary.
    """

    def __init__(
        self,
        command: str = str(SCIFIREADERS_MCP_COMMAND),
        tool_name: str = "read_scifireaders_file",
    ) -> None:
        self.command = str(command)
        self.tool_name = tool_name

    async def read_file(
        self,
        file_path: str,
        return_mode: str = "data",
    ) -> dict[str, Any]:
        """
        Read an SPM file through the SciFiReaders MCP tool.

        Parameters
        ----------
        file_path : str
            Path to the source SPM file.
        return_mode : str
            SciFiReaders MCP return mode. Usually "data", "file", or "both".

        Returns
        -------
        dict
            Parsed SciFiReaders payload.
        """
        server_params = StdioServerParameters(
            command=self.command,
            args=[],
        )

        async with stdio_client(
            server_params,
            errlog=subprocess.DEVNULL,  # important for Windows + Jupyter
        ) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()

                result = await session.call_tool(
                    self.tool_name,
                    {
                        "file_path": file_path,
                        "return_mode": return_mode,
                    },
                )

        return self._parse_mcp_result(result)

    def _parse_mcp_result(self, result: Any) -> dict[str, Any]:
        """
        Convert MCP CallToolResult into a Python dictionary.
        """
        # MCP error result
        is_error = (
            getattr(result, "isError", False)
            or getattr(result, "is_error", False)
        )

        if is_error:
            raise RuntimeError(
                "SciFiReaders MCP tool returned an error:\n"
                f"{self._summarize_result(result)}"
            )

        # Case 1: structured content, if available
        structured_content = getattr(result, "structuredContent", None)
        if structured_content is not None:
            if isinstance(structured_content, dict):
                return structured_content

            try:
                return dict(structured_content)
            except Exception:
                pass

        structured_content = getattr(result, "structured_content", None)
        if structured_content is not None:
            if isinstance(structured_content, dict):
                return structured_content

            try:
                return dict(structured_content)
            except Exception:
                pass

        # Case 2: JSON text content
        content = getattr(result, "content", None)

        if not content:
            raise ValueError(
                "SciFiReaders MCP tool returned no content.\n"
                f"Raw result:\n{self._summarize_result(result)}"
            )

        first_item = content[0]
        text = getattr(first_item, "text", None)

        if text is None:
            raise ValueError(
                "SciFiReaders MCP result content has no text field.\n"
                f"First content item:\n{repr(first_item)}\n\n"
                f"Raw result:\n{self._summarize_result(result)}"
            )

        if not text.strip():
            raise ValueError(
                "SciFiReaders MCP tool returned empty text content.\n"
                f"Raw result:\n{self._summarize_result(result)}"
            )

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise ValueError(
                "SciFiReaders MCP tool returned text, but it is not valid JSON.\n\n"
                f"First 1000 characters of returned text:\n{repr(text[:1000])}\n\n"
                f"Raw MCP result:\n{self._summarize_result(result)}"
            ) from exc

    @staticmethod
    def _summarize_result(result: Any, max_len: int = 2000) -> str:
        """
        Return a shortened debug representation of an MCP result.
        """
        text = repr(result)

        if len(text) > max_len:
            text = text[:max_len] + "... <truncated>"

        return text