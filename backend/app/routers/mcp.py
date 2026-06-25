from fastapi import APIRouter

from ..services.mcp import MCP_SERVER_INFO, build_mcp_tools, call_mcp_tool, make_mcp_response


def build_mcp_router(**deps):
    router = APIRouter()

    @router.get("/mcp")
    def mcp_info():
        return {
            "name": MCP_SERVER_INFO["name"],
            "version": MCP_SERVER_INFO["version"],
            "endpoint": "/mcp",
            "transport": "jsonrpc-http",
        }

    @router.post("/mcp")
    def mcp_rpc(message: dict):
        try:
            method = message.get("method")
            msg_id = message.get("id")

            if msg_id is None:
                return {}

            if method == "initialize":
                return make_mcp_response(
                    msg_id,
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": MCP_SERVER_INFO,
                    },
                )

            if method == "ping":
                return make_mcp_response(msg_id, {})

            if method == "tools/list":
                return make_mcp_response(msg_id, {"tools": build_mcp_tools()})

            if method == "tools/call":
                params = message.get("params", {})
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                if not tool_name:
                    return make_mcp_response(
                        msg_id,
                        error={"code": -32602, "message": "Missing tool name"},
                    )
                return make_mcp_response(msg_id, call_mcp_tool(tool_name, tool_args, **deps))

            return make_mcp_response(
                msg_id,
                error={"code": -32601, "message": f"Unknown method: {method}"},
            )
        except Exception as exc:
            return make_mcp_response(
                message.get("id"),
                error={"code": -32000, "message": str(exc)},
            )

    return router
