# mcp_client.py
from contextlib import asynccontextmanager

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

KAPRUKA_MCP_URL = "https://mcp.kapruka.com/mcp"


@asynccontextmanager
async def kapruka_session():
    """Open a connection to the Kapruka MCP server for one request."""
    async with streamablehttp_client(KAPRUKA_MCP_URL) as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()  # the MCP handshake
            yield session


def mcp_tools_to_openai(tools_result) -> list[dict]:
    """Translate MCP tool schemas into OpenAI function-calling format."""
    return [
        {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description or "",
                "parameters": t.inputSchema,
            },
        }
        for t in tools_result.tools
    ]
