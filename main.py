# main.py

import asyncio
import os
from multiprocessing import Process
from mcp.server.fastmcp import FastMCP
from mcp_client import run_client  # Your async client runner from client.py

def run_server():
    """Launch the MCP server with SSE transport."""
    from mcp_server import mcp  # Import the FastMCP instance
    mcp.run(transport='sse')

async def main():
    """Start server first, then run the client."""
    # Run server in a separate process
    server_process = Process(target=run_server)
    server_process.start()

    try:
        # Give server a moment to spin up
        await asyncio.sleep(2)

        # Start client interaction
        await run_client()

    finally:
        # Clean up: terminate server when done
        server_process.terminate()
        server_process.join()

if __name__ == "__main__":
    asyncio.run(main())
