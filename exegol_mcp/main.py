#!/usr/bin/env python3
"""
Exegol MCP Server - Main Entry Point

A Model Context Protocol server for interacting with Exegol pentesting containers.
"""

import asyncio
import json
import logging
import sys
import time
from typing import Any, Dict

# MCP SDK imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Local imports
from .config import load_config
from .exceptions import ExegolMCPError
from .logging_setup import setup_logging
from .handlers import (
    handle_exegol_exec,
    handle_exegol_list,
    handle_exegol_status,
    handle_list_workflows,
    handle_run_workflow,
)
from .models import Config, MCPResponse, ErrorDetails
from .session_manager import SessionManager, SessionConfig

# Global state
config: Config = None
logger: logging.Logger = None
server_start_time: float = 0.0
session_manager: SessionManager = None


async def main() -> None:
    """Main entry point for MCP server."""
    global config, logger, server_start_time, session_manager

    # Load configuration
    try:
        config = load_config("config.yaml")
    except ExegolMCPError as e:
        print(f"Configuration error: {e.message}", file=sys.stderr)
        print(f"Details: {e.details}", file=sys.stderr)
        print(f"Remediation: {e.remediation}", file=sys.stderr)
        sys.exit(1)

    # Setup logging
    logger = setup_logging(config)
    server_start_time = time.time()

    # Initialize session manager if persistent sessions are enabled
    if config.use_persistent_sessions:
        session_config = SessionConfig(
            exegol_path=config.exegol_path,
            default_timeout=config.command_timeout,
            session_idle_timeout=config.session_idle_timeout,
        )
        session_manager = SessionManager(session_config)
        await session_manager.start_cleanup_task()
        logger.info("Persistent sessions enabled with automatic cleanup")

    logger.info(
        "Exegol MCP Server starting",
        extra={
            "server_version": config.server_version,
            "exegol_path": config.exegol_path,
            "persistent_sessions": config.use_persistent_sessions,
        },
    )

    # Initialize MCP Server
    server = Server(config.server_name)

    logger.info("Registering MCP tools")

    # Register tools
    @server.list_tools()
    async def list_tools_handler() -> list[Tool]:
        """List available MCP tools."""
        return [
            Tool(
                name="exegol_exec",
                description="Execute a command in an Exegol container. ⚠️ WARNING: Commands are NOT sanitized. Security relies on container isolation.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "container_name": {
                            "type": "string",
                            "description": "Name of the Exegol container to execute the command in",
                        },
                        "command": {
                            "type": "string",
                            "description": "Command to execute (NOT sanitized - use with caution)",
                        },
                    },
                    "required": ["container_name", "command"],
                },
            ),
            Tool(
                name="exegol_list",
                description="List all available Exegol containers on the system with their status, image, and creation date.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="exegol_status",
                description="Check MCP server health status, including Exegol availability, server uptime, and configuration.",
                inputSchema={
                    "type": "object",
                    "properties": {},
                },
            ),
            Tool(
                name="list_workflows",
                description="List all available predefined pentest workflows with optional filtering by category, difficulty, or tags.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Filter by category (recon, enumeration, vulnerability_scan, exploitation, post_exploitation, web, network)",
                            "enum": ["recon", "enumeration", "vulnerability_scan", "exploitation", "post_exploitation", "web", "network"],
                        },
                        "difficulty": {
                            "type": "string",
                            "description": "Filter by difficulty level",
                            "enum": ["easy", "medium", "hard"],
                        },
                        "tags": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Filter by tags (any match)",
                        },
                    },
                },
            ),
            Tool(
                name="run_workflow",
                description="Execute a predefined pentest workflow in an Exegol container. The workflow will run multiple steps sequentially with the provided parameters.",
                inputSchema={
                    "type": "object",
                    "properties": {
                        "workflow_name": {
                            "type": "string",
                            "description": "Name of the workflow to execute (use list_workflows to see available workflows)",
                        },
                        "container_name": {
                            "type": "string",
                            "description": "Name of the Exegol container to execute the workflow in",
                        },
                        "params": {
                            "type": "object",
                            "description": "Workflow parameters as key-value pairs (required params depend on the workflow)",
                            "additionalProperties": {"type": "string"},
                        },
                    },
                    "required": ["workflow_name", "container_name", "params"],
                },
            ),
        ]

    @server.call_tool()
    async def call_tool_handler(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
        """Handle tool execution requests."""
        logger.info(f"Tool called: {name}", extra={"tool": name, "arguments": arguments})

        try:
            if name == "exegol_exec":
                container_name = arguments.get("container_name", "")
                command = arguments.get("command", "")
                response = await handle_exegol_exec(
                    container_name, command, config, session_manager, server_start_time
                )

            elif name == "exegol_list":
                response = await handle_exegol_list(config)

            elif name == "exegol_status":
                response = await handle_exegol_status(config, server_start_time)

            elif name == "list_workflows":
                category = arguments.get("category")
                difficulty = arguments.get("difficulty")
                tags = arguments.get("tags")
                response = await handle_list_workflows(category, difficulty, tags)

            elif name == "run_workflow":
                workflow_name = arguments.get("workflow_name", "")
                container_name = arguments.get("container_name", "")
                params = arguments.get("params", {})
                response = await handle_run_workflow(
                    workflow_name, container_name, params, config, session_manager
                )

            else:
                response = MCPResponse(
                    success=False,
                    error=ErrorDetails(
                        error_code="UNKNOWN_TOOL",
                        message=f"Unknown tool: {name}",
                        details=f"The tool '{name}' is not recognized by this server",
                        remediation="Use list_tools to see available tools",
                    ),
                )

            # Convert response to TextContent (use compact mode if configured)
            return [TextContent(
                type="text",
                text=json.dumps(response.to_dict(compact=config.compact_mode), indent=2),
            )]

        except Exception as e:
            logger.exception(f"Error executing tool {name}")
            error_response = MCPResponse(
                success=False,
                error=ErrorDetails(
                    error_code="TOOL_EXECUTION_ERROR",
                    message=str(e),
                    details=f"An error occurred while executing {name}",
                    remediation="Check server logs for details",
                ),
            )
            return [TextContent(
                type="text",
                text=json.dumps(error_response.to_dict(compact=config.compact_mode), indent=2),
            )]

    logger.info(
        "MCP server initialized",
        extra={
            "tools_registered": 5,
            "server_name": config.server_name,
            "server_version": config.server_version,
        },
    )

    print("✓ Configuration loaded successfully", file=sys.stderr)
    print(f"✓ Server: {config.server_name} v{config.server_version}", file=sys.stderr)
    print(f"✓ Exegol path: {config.exegol_path}", file=sys.stderr)
    print(f"✓ Timeout: {config.command_timeout}s", file=sys.stderr)
    print("✓ Tools registered: exegol_exec, exegol_list, exegol_status, list_workflows, run_workflow", file=sys.stderr)
    print("\n🚀 MCP server running on stdio...", file=sys.stderr)

    # Run the server with stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


def run():
    """Entry point wrapper for package execution."""
    asyncio.run(main())


if __name__ == "__main__":
    run()
