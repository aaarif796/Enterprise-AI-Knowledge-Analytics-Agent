"""MCP Server - exposes the tool registry to MCP-compatible clients."""
from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .tools import get_registry


class ToolCall(BaseModel):
    name: str
    arguments: dict[str, Any] = {}


class MCPServer:
    """Minimal MCP server exposing list/call endpoints."""

    def __init__(self) -> None:
        self.registry = get_registry()
        self.router = APIRouter(prefix="/mcp", tags=["mcp"])
        self.router.add_api_route("/tools", self._list_tools, methods=["GET"])
        self.router.add_api_route("/tools/call", self._call_tool, methods=["POST"])
        self.router.add_api_route("/tools/{name}", self._call_named, methods=["POST"])

    async def _list_tools(self) -> JSONResponse:
        return JSONResponse({"tools": self.registry.list()})

    async def _call_tool(self, payload: ToolCall) -> JSONResponse:
        return await self._dispatch(payload.name, payload.arguments)

    async def _call_named(self, name: str, payload: ToolCall) -> JSONResponse:
        return await self._dispatch(name, payload.arguments)

    async def _dispatch(self, name: str, arguments: dict[str, Any]) -> JSONResponse:
        try:
            result = await self.registry.call(name, **arguments)
            return JSONResponse({"ok": True, "result": result})
        except Exception as exc:
            return JSONResponse({"ok": False, "error": str(exc)}, status_code=400)


def get_mcp_server() -> MCPServer:
    return MCPServer()
