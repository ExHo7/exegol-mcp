"""
Exegol MCP Server Package

A Model Context Protocol server for interacting with Exegol pentesting containers.
"""

__version__ = "0.1.0"
__author__ = "Cyber_fish"

from .exceptions import (
    ExegolMCPError,
    ExegolNotFoundError,
    ContainerNotFoundError,
    ContainerNotRunningError,
    CommandTimeoutError,
    CommandExecutionError,
    ConfigurationError,
    InvalidInputError,
)

from .models import (
    Config,
    ErrorDetails,
    MCPResponse,
    CommandExecution,
    Container,
    ServerStatus,
)

from .config import load_config
from .utils import truncate_output
from .cli_wrappers import (
    exec_exegol_command,
    list_exegol_containers,
    check_exegol_version,
    exec_via_session,
)
from .session_manager import SessionManager, SessionConfig, ExegolSession, SessionMetrics
from .handlers import handle_exegol_exec, handle_exegol_list, handle_exegol_status
from .logging_setup import setup_logging, JSONFormatter

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
    # Session
    "SessionManager",
    "SessionConfig",
    "ExegolSession",
    "SessionMetrics",
]
