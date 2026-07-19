from mcp import types
from mcp.server.fastmcp import FastMCP

from ..services.mcp import MCP_SERVER_INFO, build_mcp_tools, call_mcp_tool


def build_mcp_app(**deps):
    """Build the SDK-backed, stateless Streamable HTTP MCP application."""
    mcp = FastMCP(
        MCP_SERVER_INFO["name"],
        instructions="Read and update the local Training Dashboard.",
        json_response=True,
        stateless_http=True,
        streamable_http_path="/",
    )

    @mcp._mcp_server.list_tools()
    async def list_tools():
        return [types.Tool.model_validate(tool) for tool in build_mcp_tools()]

    @mcp._mcp_server.call_tool()
    async def dispatch_tool(name: str, arguments: dict):
        return types.CallToolResult.model_validate(call_mcp_tool(name, arguments, **deps))

    return mcp.streamable_http_app()
