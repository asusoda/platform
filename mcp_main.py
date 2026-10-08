"""Run the MCP server (streamable HTTP on /mcp, port MCP_PORT or 8001).

Clients authenticate with a machine token: Authorization: Bearer plat_...
"""

import os

import uvicorn

from modules.mcp.server import build_app
from modules.registry import load_tools
from shared import logger


def main() -> None:
    load_tools()
    port = int(os.environ.get("MCP_PORT", "8001"))
    logger.info("Starting MCP server on port %s", port)
    uvicorn.run(build_app(), host="0.0.0.0", port=port, log_level="info")  # nosec B104


if __name__ == "__main__":
    main()
