#!/usr/bin/env python3
"""
Exegol MCP Server - Compatibility Wrapper

This file maintains backward compatibility with the old monolithic structure.
It simply imports and re-exports everything from the exegol_mcp package.
"""

# Re-export everything for backward compatibility
from exegol_mcp.exceptions import *
from exegol_mcp.models import *
from exegol_mcp.config import load_config
from exegol_mcp.utils import truncate_output
from exegol_mcp.cli_wrappers import (
    exec_exegol_command,
    list_exegol_containers,
    check_exegol_version,
    exec_via_session,
)
from exegol_mcp.session_manager import (
    SessionManager,
    SessionConfig,
    ExegolSession,
    SessionMetrics,
)
from exegol_mcp.handlers import (
    handle_exegol_exec,
    handle_exegol_list,
    handle_exegol_status,
)
from exegol_mcp.logging_setup import setup_logging, JSONFormatter
from exegol_mcp.main import main

__all__ = [
    # Exceptions
    "ExegolMCPError",
    "ExegolNotFoundError",
    "ContainerNotFoundError",
    "ContainerNotRunningError",
    "CommandTimeoutError",
    "CommandExecutionError",
    "ConfigurationError",
    "InvalidInputError",
    # Models
    "Config",
    "ErrorDetails",
    "MCPResponse",
    "CommandExecution",
    "Container",
    "ServerStatus",
    # Functions
    "load_config",
    "truncate_output",
    "exec_exegol_command",
    "list_exegol_containers",
    "check_exegol_version",
    "exec_via_session",
    "handle_exegol_exec",
    "handle_exegol_list",
    "handle_exegol_status",
    "setup_logging",
    "JSONFormatter",
    "main",
    # Session manager
    "SessionManager",
    "SessionConfig",
    "ExegolSession",
    "SessionMetrics",
]

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
