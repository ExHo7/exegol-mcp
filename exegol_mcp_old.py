#!/usr/bin/env python3
"""
Exegol MCP Server

A Model Context Protocol server for interacting with Exegol pentesting containers.
Enables AI agents to execute commands, list containers, and check server health.

Author: Cyber_fish
License: See LICENSE file
Version: 0.1.0
"""

import asyncio
import json
import logging
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

# MCP SDK imports
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import Tool, TextContent

# Session manager import
from session_manager import SessionManager, SessionConfig


# ============================================================================
# CUSTOM EXCEPTIONS
# ============================================================================


class ExegolMCPError(Exception):
    """Base exception for all Exegol MCP errors."""

    error_code: str = "UNKNOWN_ERROR"

    def __init__(self, message: str, details: str = "", remediation: str = "") -> None:
        super().__init__(message)
        self.message = message
        self.details = details
        self.remediation = remediation


class ExegolNotFoundError(ExegolMCPError):
    """Raised when Exegol CLI is not found or not accessible."""

    error_code = "EXEGOL_NOT_FOUND"

    def __init__(self, path: str) -> None:
        super().__init__(
            message=f"Exegol CLI not found at '{path}'",
            details="The Exegol command-line tool is not accessible at the configured path",
            remediation="Install Exegol from https://github.com/ThePorgs/Exegol and update 'exegol_path' in config.yaml",
        )


class ContainerNotFoundError(ExegolMCPError):
    """Raised when specified container does not exist."""

    error_code = "CONTAINER_NOT_FOUND"

    def __init__(self, container_name: str) -> None:
        super().__init__(
            message=f"Container '{container_name}' not found",
            details=f"No Exegol container with name '{container_name}' exists on this system",
            remediation="Run 'exegol info' to list available containers, or create a new container with 'exegol install'",
        )
        self.container_name = container_name


class ContainerNotRunningError(ExegolMCPError):
    """Raised when container exists but is not in running state."""

    error_code = "CONTAINER_NOT_RUNNING"

    def __init__(self, container_name: str, status: str) -> None:
        super().__init__(
            message=f"Container '{container_name}' is not running (status: {status})",
            details=f"The container exists but is in '{status}' state",
            remediation=f"Start the container with 'exegol start {container_name}'",
        )
        self.container_name = container_name
        self.status = status


class CommandTimeoutError(ExegolMCPError):
    """Raised when command execution exceeds timeout."""

    error_code = "COMMAND_TIMEOUT"

    def __init__(self, timeout_seconds: int, partial_output: str = "") -> None:
        super().__init__(
            message=f"Command exceeded {timeout_seconds}s timeout",
            details=f"Command execution was terminated after {timeout_seconds} seconds",
            remediation="Use shorter commands or split long operations into multiple steps",
        )
        self.timeout_seconds = timeout_seconds
        self.partial_output = partial_output


class CommandExecutionError(ExegolMCPError):
    """Raised when command execution fails (general error)."""

    error_code = "COMMAND_EXECUTION_ERROR"


class ConfigurationError(ExegolMCPError):
    """Raised when configuration is invalid."""

    error_code = "CONFIGURATION_ERROR"


class InvalidInputError(ExegolMCPError):
    """Raised when tool parameters are invalid."""

    error_code = "INVALID_INPUT"


# ============================================================================
# DATA MODELS
# ============================================================================


@dataclass
class Config:
    """Server configuration loaded from config.yaml."""

    exegol_path: str
    command_timeout: int = 180
    log_level: str = "INFO"
    log_format: str = "json"
    server_name: str = "exegol-mcp-server"
    server_version: str = "0.1.0"
    compact_mode: bool = False
    use_persistent_sessions: bool = False
    session_idle_timeout: int = 300

    def __post_init__(self) -> None:
        """Validate configuration values."""
        # Validate timeout
        if not (1 <= self.command_timeout <= 3600):
            raise ConfigurationError(
                "command_timeout must be between 1 and 3600 seconds",
                details=f"Got: {self.command_timeout}",
                remediation="Update command_timeout in config.yaml to a value between 1-3600",
            )

        # Validate log level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR"]
        if self.log_level.upper() not in valid_levels:
            raise ConfigurationError(
                f"Invalid log_level: {self.log_level}",
                details=f"Must be one of: {', '.join(valid_levels)}",
                remediation=f"Update log_level in config.yaml to one of: {', '.join(valid_levels)}",
            )

        # Validate log format
        if self.log_format not in ["json", "text"]:
            raise ConfigurationError(
                f"Invalid log_format: {self.log_format}",
                details="Must be 'json' or 'text'",
                remediation="Update log_format in config.yaml to 'json' or 'text'",
            )

    @classmethod
    def from_yaml(cls, path: str = "config.yaml") -> "Config":
        """Load configuration from YAML file.

        Args:
            path: Path to config.yaml file

        Returns:
            Config instance

        Raises:
            ConfigurationError: If file not found or invalid YAML
        """
        config_path = Path(path)
        if not config_path.exists():
            raise ConfigurationError(
                f"Configuration file not found: {path}",
                details="The config.yaml file is required for server operation",
                remediation="Create config.yaml based on the provided example",
            )

        try:
            with open(config_path, "r") as f:
                data = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigurationError(
                "Invalid YAML in configuration file",
                details=str(e),
                remediation="Fix YAML syntax errors in config.yaml",
            )

        # Extract values with defaults
        return cls(
            exegol_path=data.get("exegol", {}).get("path", "exegol"),
            command_timeout=data.get("timeout", {}).get("command_execution", 180),
            log_level=data.get("logging", {}).get("level", "INFO"),
            log_format=data.get("logging", {}).get("format", "json"),
            server_name=data.get("mcp", {}).get("server_name", "exegol-mcp-server"),
            server_version=data.get("mcp", {}).get("version", "0.1.0"),
            compact_mode=data.get("mcp", {}).get("compact_mode", False),
            use_persistent_sessions=data.get("sessions", {}).get("enabled", False),
            session_idle_timeout=data.get("sessions", {}).get("idle_timeout", 300),
        )


@dataclass
class ErrorDetails:
    """Structured error information for MCP responses."""

    error_code: str
    message: str
    details: str = ""
    remediation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "details": self.details,
            "remediation": self.remediation,
        }


@dataclass
class MCPResponse:
    """Standard response format for all MCP tool invocations."""

    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[ErrorDetails] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self, compact: bool = False) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization.

        Args:
            compact: If True, use compact format to reduce token usage.
                     Compact mode simplifies field names and omits metadata.

        Returns:
            Dictionary representation of the response
        """
        if compact:
            # Compact mode: minimal keys, no metadata
            if self.success:
                # Success: only return "ok" and data (data fields merged at root level)
                if self.data:
                    return {"ok": True, **self.data}
                else:
                    return {"ok": True}
            else:
                # Error: return "ok": False and simplified error info
                if self.error:
                    return {
                        "ok": False,
                        "err": self.error.message,
                        "code": self.error.error_code,
                        "fix": self.error.remediation,
                    }
                else:
                    return {"ok": False, "err": "Unknown error"}

        # Standard mode (current format)
        result: Dict[str, Any] = {"success": self.success, "metadata": self.metadata}
        if self.data is not None:
            result["data"] = self.data
        if self.error is not None:
            result["error"] = self.error.to_dict()
        return result


@dataclass
class CommandExecution:
    """Represents a command execution request and its result."""

    container_name: str
    command: str
    stdout: str = ""
    stderr: str = ""
    exit_code: Optional[int] = None
    execution_time_ms: int = 0
    timed_out: bool = False
    stdout_truncated: bool = False
    stderr_truncated: bool = False
    original_stdout_lines: int = 0
    original_stderr_lines: int = 0

    def is_success(self) -> bool:
        """Check if command succeeded."""
        return self.exit_code == 0 and not self.timed_out

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MCP response."""
        result = {
            "container_name": self.container_name,
            "command": self.command,
            "stdout": self.stdout,
            "stderr": self.stderr,
            "exit_code": self.exit_code,
            "execution_time_ms": self.execution_time_ms,
            "timed_out": self.timed_out,
        }

        # Add truncation info if outputs were truncated
        if self.stdout_truncated:
            result["stdout_truncated"] = True
            result["original_stdout_lines"] = self.original_stdout_lines
        if self.stderr_truncated:
            result["stderr_truncated"] = True
            result["original_stderr_lines"] = self.original_stderr_lines

        return result


@dataclass
class Container:
    """Represents an Exegol container with its metadata."""

    name: str
    status: str
    image: str
    created: str
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_exegol_info(cls, line: str) -> Optional["Container"]:
        """
        Parse a line from 'exegol info' output to create Container object.

        Expected format: NAME STATUS IMAGE CREATED
        Example: test-container running full:latest 2024-01-15

        Args:
            line: Single line from exegol info output

        Returns:
            Container object or None if parsing fails
        """
        if not line or not line.strip():
            return None

        parts = line.split()
        if len(parts) < 4:
            return None

        # Skip header line
        if parts[0].upper() == "NAME":
            return None

        return cls(
            name=parts[0],
            status=parts[1],
            image=parts[2],
            created=parts[3] if len(parts) > 3 else "",
            metadata={},
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MCP response."""
        return {
            "name": self.name,
            "status": self.status,
            "image": self.image,
            "created": self.created,
            "metadata": self.metadata,
        }


@dataclass
class ServerStatus:
    """Represents MCP server status and health information."""

    server_name: str
    server_version: str
    exegol_available: bool
    exegol_version: Optional[str]
    uptime_seconds: float
    timestamp: str
    configuration: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for MCP response."""
        return {
            "server_name": self.server_name,
            "server_version": self.server_version,
            "exegol_available": self.exegol_available,
            "exegol_version": self.exegol_version,
            "uptime_seconds": self.uptime_seconds,
            "timestamp": self.timestamp,
            "configuration": self.configuration,
        }


# ============================================================================
# LOGGING SETUP
# ============================================================================


class JSONFormatter(logging.Formatter):
    """JSON log formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON."""
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "level": record.levelname,
            "component": record.name,
            "message": record.getMessage(),
        }

        # Add extra fields if present
        if hasattr(record, "container_name"):
            log_data["container_name"] = record.container_name
        if hasattr(record, "command"):
            log_data["command"] = record.command
        if hasattr(record, "exit_code"):
            log_data["exit_code"] = record.exit_code
        if hasattr(record, "execution_time_ms"):
            log_data["execution_time_ms"] = record.execution_time_ms

        return json.dumps(log_data)


def setup_logging(config: Config) -> logging.Logger:
    """Setup structured logging based on configuration.

    Args:
        config: Server configuration

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("exegol_mcp")
    logger.setLevel(getattr(logging, config.log_level.upper()))

    # Remove existing handlers
    logger.handlers.clear()

    # Create handler
    handler = logging.StreamHandler(sys.stderr)

    # Set formatter based on config
    if config.log_format == "json":
        handler.setFormatter(JSONFormatter())
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )

    logger.addHandler(handler)
    return logger


# ============================================================================
# GLOBAL STATE
# ============================================================================

config: Optional[Config] = None
logger: Optional[logging.Logger] = None
server_start_time: float = 0.0
session_manager: Optional[SessionManager] = None


# ============================================================================
# OUTPUT UTILITIES
# ============================================================================


def truncate_output(
    output: str,
    max_lines: int = 100,
    max_chars: int = 5000,
    context_lines: int = 10,
) -> tuple[str, bool, int]:
    """
    Truncate output to save tokens while preserving useful context.

    Strategy:
    - Keep first N lines (beginning of output)
    - Keep last N lines (end of output, often contains errors/results)
    - Add clear truncation indicator in the middle

    Args:
        output: The output string to potentially truncate
        max_lines: Maximum number of lines to keep (default: 100)
        max_chars: Maximum number of characters to keep (default: 5000)
        context_lines: Number of lines to keep from start and end (default: 10)

    Returns:
        Tuple of (truncated_output, was_truncated, original_line_count)
    """
    if not output:
        return output, False, 0

    lines = output.split("\n")
    original_line_count = len(lines)
    was_truncated = False

    # Check if truncation by line count is needed
    if len(lines) > max_lines:
        # Keep context from start and end
        start_lines = lines[:context_lines]
        end_lines = lines[-context_lines:]

        truncated_count = len(lines) - (2 * context_lines)
        truncation_marker = f"\n... [{truncated_count} lines truncated for token efficiency] ...\n"

        output = "\n".join(start_lines) + truncation_marker + "\n".join(end_lines)
        was_truncated = True

    # Check if truncation by character count is needed
    if len(output) > max_chars:
        # Keep beginning and show truncation info
        char_count = len(output)
        output = output[:max_chars]
        output += f"\n\n... [truncated at {max_chars} chars, original: {char_count} chars] ..."
        was_truncated = True

    return output, was_truncated, original_line_count


# ============================================================================
# PHASE 3: EXEGOL CLI WRAPPERS
# ============================================================================


async def exec_exegol_command(
    container_name: str,
    command: str,
    cfg: Config,
    truncate: bool = True,
    max_lines: int = 100,
    max_chars: int = 5000,
) -> CommandExecution:
    """
    Execute command in Exegol container with timeout and optional output truncation.

    ⚠️ WARNING: Commands are NOT sanitized. Ensure container_name and command
    are from trusted sources. Security relies on Exegol container isolation.

    Args:
        container_name: Name of the Exegol container
        command: Command to execute (NOT sanitized)
        cfg: Configuration object with timeout and exegol path
        truncate: Enable automatic output truncation to save tokens (default: True)
        max_lines: Maximum lines to keep in output when truncating (default: 100)
        max_chars: Maximum characters to keep in output when truncating (default: 5000)

    Returns:
        CommandExecution object with stdout, stderr, exit code, and timing

    Raises:
        ExegolNotFoundError: If Exegol CLI is not found
        ContainerNotFoundError: If container doesn't exist
        CommandTimeoutError: If command exceeds timeout
    """
    # Log if logger is available (optional for testing)
    if logger:
        logger.info(
            "Executing command in container",
            extra={"container_name": container_name, "command": command},
        )

    start_time = time.time()

    # Construct Exegol command with -v flag for stdio output
    exegol_cmd = [cfg.exegol_path, "exec", "-v", container_name, command]

    try:
        # Create subprocess
        process = await asyncio.create_subprocess_exec(
            *exegol_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        # Wait for command with timeout
        try:
            stdout_bytes, stderr_bytes = await asyncio.wait_for(
                process.communicate(), timeout=cfg.command_timeout
            )
        except asyncio.TimeoutError:
            # Kill the process
            process.kill()
            await process.wait()
            execution_time = int((time.time() - start_time) * 1000)

            if logger:
                logger.warning(
                    "Command execution timed out",
                    extra={
                        "container_name": container_name,
                        "command": command,
                        "timeout_seconds": cfg.command_timeout,
                    },
                )

            raise CommandTimeoutError(cfg.command_timeout)

        # Decode output
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        stderr = stderr_bytes.decode("utf-8", errors="replace")
        exit_code = process.returncode if process.returncode is not None else -1

        execution_time = int((time.time() - start_time) * 1000)

        # Apply truncation if enabled
        stdout_truncated = False
        stderr_truncated = False
        original_stdout_lines = 0
        original_stderr_lines = 0

        if truncate:
            stdout, stdout_truncated, original_stdout_lines = truncate_output(
                stdout, max_lines=max_lines, max_chars=max_chars
            )
            # Use smaller limits for stderr (usually less important than stdout)
            stderr, stderr_truncated, original_stderr_lines = truncate_output(
                stderr, max_lines=max_lines // 2, max_chars=max_chars // 2
            )

        # Check for container not found error (specific to Exegol container errors)
        stderr_lower = stderr.lower()
        if exit_code != 0 and (
            ("container" in stderr_lower and "not found" in stderr_lower)
            or ("container" in stderr_lower and "does not exist" in stderr_lower)
        ):
            if logger:
                logger.error(
                    "Container not found",
                    extra={"container_name": container_name, "stderr": stderr},
                )
            raise ContainerNotFoundError(container_name)

        # Log result
        if logger:
            logger.info(
                "Command execution completed",
                extra={
                    "container_name": container_name,
                    "command": command,
                    "exit_code": exit_code,
                    "execution_time_ms": execution_time,
                },
            )

        return CommandExecution(
            container_name=container_name,
            command=command,
            stdout=stdout,
            stderr=stderr,
            exit_code=exit_code,
            execution_time_ms=execution_time,
            timed_out=False,
            stdout_truncated=stdout_truncated,
            stderr_truncated=stderr_truncated,
            original_stdout_lines=original_stdout_lines,
            original_stderr_lines=original_stderr_lines,
        )

    except FileNotFoundError:
        if logger:
            logger.error(
                "Exegol CLI not found",
                extra={"exegol_path": cfg.exegol_path},
            )
        raise ExegolNotFoundError(cfg.exegol_path)


async def list_exegol_containers(cfg: Config) -> List[Container]:
    """
    List all Exegol containers on the system.

    Args:
        cfg: Configuration object with exegol path

    Returns:
        List of Container objects (empty list if no containers)

    Raises:
        ExegolNotFoundError: If Exegol CLI is not found
    """
    if logger:
        logger.info("Listing Exegol containers")

    # Construct Exegol command
    exegol_cmd = [cfg.exegol_path, "info"]

    try:
        # Create subprocess
        process = await asyncio.create_subprocess_exec(
            *exegol_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_bytes, stderr_bytes = await process.communicate()

        # Decode output
        stdout = stdout_bytes.decode("utf-8", errors="replace")
        exit_code = process.returncode if process.returncode is not None else -1

        if exit_code != 0:
            if logger:
                logger.warning(
                    "exegol info returned non-zero exit code",
                    extra={"exit_code": exit_code, "stderr": stderr_bytes.decode()},
                )

        # Parse output lines to Container objects
        containers: List[Container] = []
        for line in stdout.split("\n"):
            container = Container.from_exegol_info(line)
            if container:
                containers.append(container)

        if logger:
            logger.info(
                "Container listing completed",
                extra={"total_containers": len(containers)},
            )

        return containers

    except FileNotFoundError:
        if logger:
            logger.error(
                "Exegol CLI not found",
                extra={"exegol_path": cfg.exegol_path},
            )
        raise ExegolNotFoundError(cfg.exegol_path)


async def check_exegol_version(cfg: Config) -> Optional[str]:
    """
    Check if Exegol CLI is available and get its version.

    Args:
        cfg: Configuration object with exegol path

    Returns:
        Version string if Exegol is available, None otherwise
    """
    if logger:
        logger.debug("Checking Exegol version")

    # Construct Exegol command
    exegol_cmd = [cfg.exegol_path, "--version"]

    try:
        # Create subprocess
        process = await asyncio.create_subprocess_exec(
            *exegol_cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )

        stdout_bytes, stderr_bytes = await process.communicate()

        # Decode output
        stdout = stdout_bytes.decode("utf-8", errors="replace").strip()

        if logger:
            logger.debug(
                "Exegol version check completed",
                extra={"version": stdout},
            )

        return stdout if stdout else None

    except FileNotFoundError:
        if logger:
            logger.debug(
                "Exegol CLI not found",
                extra={"exegol_path": cfg.exegol_path},
            )
        return None


# ============================================================================
# SESSION-BASED EXECUTION
# ============================================================================


async def exec_via_session(
    container_name: str,
    command: str,
    cfg: Config,
    truncate: bool = True,
    max_lines: int = 100,
    max_chars: int = 5000,
) -> CommandExecution:
    """
    Execute command via persistent session.

    Args:
        container_name: Name of the Exegol container
        command: Command to execute
        cfg: Configuration object
        truncate: Enable automatic output truncation (default: True)
        max_lines: Maximum lines to keep in output when truncating (default: 100)
        max_chars: Maximum characters to keep in output when truncating (default: 5000)

    Returns:
        CommandExecution object with results

    Raises:
        RuntimeError: If session_manager is not initialized
    """
    if not session_manager:
        raise RuntimeError("Session manager is not initialized")

    # Get or create session for this container
    session = await session_manager.get_or_create_session(container_name)

    # Execute command in session
    result = await session.exec(command, timeout=cfg.command_timeout)

    # Apply truncation if enabled
    stdout = result["stdout"]
    stderr = result.get("stderr", "")
    stdout_truncated = False
    stderr_truncated = False
    original_stdout_lines = 0
    original_stderr_lines = 0

    if truncate:
        stdout, stdout_truncated, original_stdout_lines = truncate_output(
            stdout, max_lines=max_lines, max_chars=max_chars
        )
        stderr, stderr_truncated, original_stderr_lines = truncate_output(
            stderr, max_lines=max_lines // 2, max_chars=max_chars // 2
        )

    return CommandExecution(
        container_name=container_name,
        command=command,
        stdout=stdout,
        stderr=stderr,
        exit_code=result["exit_code"],
        execution_time_ms=result["execution_time_ms"],
        timed_out=result["timed_out"],
        stdout_truncated=stdout_truncated,
        stderr_truncated=stderr_truncated,
        original_stdout_lines=original_stdout_lines,
        original_stderr_lines=original_stderr_lines,
    )


# ============================================================================
# MCP TOOL HANDLERS
# ============================================================================


async def handle_exegol_exec(
    container_name: str, command: str, cfg: Config
) -> MCPResponse:
    """
    MCP tool handler for exegol_exec.

    ⚠️ WARNING: Commands are NOT sanitized. This tool executes commands directly
    in Exegol containers without any input validation or sanitization. Security
    relies entirely on container isolation.

    Args:
        container_name: Name of the Exegol container
        command: Command to execute (NOT sanitized)
        cfg: Configuration object

    Returns:
        MCPResponse with CommandExecution data or error details
    """
    # Validate inputs
    if not container_name or not container_name.strip():
        raise InvalidInputError(
            "container_name is required and cannot be empty",
            details="Parameter 'container_name' must be a non-empty string",
            remediation="Provide a valid Exegol container name",
        )

    if not command or not command.strip():
        raise InvalidInputError(
            "command is required and cannot be empty",
            details="Parameter 'command' must be a non-empty string",
            remediation="Provide a valid command to execute",
        )

    if logger:
        logger.info(
            "MCP tool exegol_exec invoked",
            extra={"container_name": container_name, "command": command},
        )

    try:
        # Use persistent sessions if enabled, otherwise use direct execution
        if cfg.use_persistent_sessions and session_manager:
            result = await exec_via_session(container_name, command, cfg)
        else:
            result = await exec_exegol_command(container_name, command, cfg)

        # Return success response with execution data
        return MCPResponse(
            success=True,
            data=result.to_dict(),
            metadata={
                "tool": "exegol_exec",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "used_session": cfg.use_persistent_sessions,
            },
        )

    except (
        ExegolNotFoundError,
        ContainerNotFoundError,
        CommandTimeoutError,
        ContainerNotRunningError,
        CommandExecutionError,
    ) as e:
        # Handle known errors
        if logger:
            logger.error(
                f"Tool execution failed: {e.error_code}",
                extra={
                    "container_name": container_name,
                    "command": command,
                    "error_code": e.error_code,
                },
            )

        return MCPResponse(
            success=False,
            error=ErrorDetails(
                error_code=e.error_code,
                message=e.message,
                details=e.details,
                remediation=e.remediation,
            ),
            metadata={
                "tool": "exegol_exec",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )

    except Exception as e:
        # Handle unexpected errors
        if logger:
            logger.exception(
                "Unexpected error in exegol_exec",
                extra={"container_name": container_name, "command": command},
            )

        return MCPResponse(
            success=False,
            error=ErrorDetails(
                error_code="UNKNOWN_ERROR",
                message=str(e),
                details="An unexpected error occurred during command execution",
                remediation="Check server logs for details",
            ),
            metadata={
                "tool": "exegol_exec",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )


async def handle_exegol_list(cfg: Config) -> MCPResponse:
    """
    MCP tool handler for exegol_list.

    Lists all available Exegol containers on the system.

    Args:
        cfg: Configuration object

    Returns:
        MCPResponse with containers array and total_count, or error details
    """
    if logger:
        logger.info("MCP tool exegol_list invoked")

    try:
        # List containers
        containers = await list_exegol_containers(cfg)

        # Convert to dict format
        containers_data = [container.to_dict() for container in containers]

        # Return success response
        return MCPResponse(
            success=True,
            data={
                "containers": containers_data,
                "total_count": len(containers),
            },
            metadata={
                "tool": "exegol_list",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )

    except ExegolNotFoundError as e:
        # Handle Exegol CLI not found
        if logger:
            logger.error(
                f"Tool execution failed: {e.error_code}",
                extra={"error_code": e.error_code},
            )

        return MCPResponse(
            success=False,
            error=ErrorDetails(
                error_code=e.error_code,
                message=e.message,
                details=e.details,
                remediation=e.remediation,
            ),
            metadata={
                "tool": "exegol_list",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )

    except Exception as e:
        # Handle unexpected errors
        if logger:
            logger.exception("Unexpected error in exegol_list")

        return MCPResponse(
            success=False,
            error=ErrorDetails(
                error_code="UNKNOWN_ERROR",
                message=str(e),
                details="An unexpected error occurred during container listing",
                remediation="Check server logs for details",
            ),
            metadata={
                "tool": "exegol_list",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )


async def handle_exegol_status(cfg: Config) -> MCPResponse:
    """
    MCP tool handler for exegol_status.

    Returns server health status, configuration, and Exegol availability.

    Args:
        cfg: Configuration object

    Returns:
        MCPResponse with ServerStatus data (always succeeds unless server broken)
    """
    if logger:
        logger.info("MCP tool exegol_status invoked")

    try:
        # Check Exegol version
        exegol_version = await check_exegol_version(cfg)
        exegol_available = exegol_version is not None

        # Calculate uptime
        uptime = time.time() - server_start_time if server_start_time > 0 else 0

        # Build ServerStatus
        status = ServerStatus(
            server_name=cfg.server_name,
            server_version=cfg.server_version,
            exegol_available=exegol_available,
            exegol_version=exegol_version,
            uptime_seconds=uptime,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            configuration={
                "exegol_path": cfg.exegol_path,
                "command_timeout": cfg.command_timeout,
                "log_level": cfg.log_level,
                "log_format": cfg.log_format,
            },
        )

        # Return success response
        return MCPResponse(
            success=True,
            data=status.to_dict(),
            metadata={
                "tool": "exegol_status",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )

    except Exception as e:
        # Handle unexpected errors (status check should rarely fail)
        if logger:
            logger.exception("Unexpected error in exegol_status")

        return MCPResponse(
            success=False,
            error=ErrorDetails(
                error_code="UNKNOWN_ERROR",
                message=str(e),
                details="An unexpected error occurred during status check",
                remediation="Check server logs for details",
            ),
            metadata={
                "tool": "exegol_status",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================


async def main() -> None:
    """Main entry point for MCP server."""
    global config, logger, server_start_time, session_manager

    # Load configuration
    try:
        config = Config.from_yaml("config.yaml")
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

    # Register exegol_exec tool
    @server.list_tools()  # type: ignore[no-untyped-call,untyped-decorator]
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
        ]

    @server.call_tool()  # type: ignore[untyped-decorator]
    async def call_tool_handler(name: str, arguments: Dict[str, Any]) -> list[TextContent]:
        """Handle tool execution requests."""
        logger.info(f"Tool called: {name}", extra={"tool": name, "arguments": arguments})

        try:
            if name == "exegol_exec":
                container_name = arguments.get("container_name", "")
                command = arguments.get("command", "")
                response = await handle_exegol_exec(container_name, command, config)

            elif name == "exegol_list":
                response = await handle_exegol_list(config)

            elif name == "exegol_status":
                response = await handle_exegol_status(config)

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
            "tools_registered": 3,
            "server_name": config.server_name,
            "server_version": config.server_version,
        },
    )

    print("✓ Configuration loaded successfully", file=sys.stderr)
    print(f"✓ Server: {config.server_name} v{config.server_version}", file=sys.stderr)
    print(f"✓ Exegol path: {config.exegol_path}", file=sys.stderr)
    print(f"✓ Timeout: {config.command_timeout}s", file=sys.stderr)
    print("✓ Tools registered: exegol_exec, exegol_list, exegol_status", file=sys.stderr)
    print("\n🚀 MCP server running on stdio...", file=sys.stderr)

    # Run the server with stdio transport
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream, server.create_initialization_options())


if __name__ == "__main__":
    asyncio.run(main())
