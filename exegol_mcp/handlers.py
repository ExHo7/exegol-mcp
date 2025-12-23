"""MCP tool handlers."""

import logging
from datetime import datetime, timezone
import time
from typing import Optional

from .models import (
    Config,
    MCPResponse,
    ErrorDetails,
    ServerStatus,
)
from .exceptions import (
    ExegolMCPError,
    ExegolNotFoundError,
    ContainerNotFoundError,
    CommandTimeoutError,
    ContainerNotRunningError,
    CommandExecutionError,
    InvalidInputError,
)
from .cli_wrappers import (
    exec_exegol_command,
    exec_via_session,
    list_exegol_containers,
    check_exegol_version,
)
from .output_parser import OutputParser

logger = logging.getLogger(__name__)


async def handle_exegol_exec(
    container_name: str,
    command: str,
    cfg: Config,
    session_manager: Optional[any] = None,
    server_start_time: float = 0.0,
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
        session_manager: Optional SessionManager instance
        server_start_time: Server start timestamp

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

    logger.info(
        f"MCP tool exegol_exec invoked for container '{container_name}'"
    )

    try:
        # Use persistent sessions if enabled, otherwise use direct execution
        if cfg.use_persistent_sessions and session_manager:
            result = await exec_via_session(
                container_name, command, cfg, session_manager
            )
        else:
            result = await exec_exegol_command(container_name, command, cfg)

        # Prepare response data
        response_data = result.to_dict()

        # Auto-parse output if enabled
        if cfg.auto_parse_output and result.stdout:
            parsed = OutputParser.auto_parse(command, result.stdout)
            if parsed.parsing_successful:
                response_data["parsed_output"] = parsed.to_dict()
                logger.info(f"Successfully parsed output as {parsed.tool_detected}")

        # Return success response with execution data
        return MCPResponse(
            success=True,
            data=response_data,
            metadata={
                "tool": "exegol_exec",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                "used_session": cfg.use_persistent_sessions,
                "auto_parsed": cfg.auto_parse_output,
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
        logger.error(f"Tool execution failed: {e.error_code}")

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
        logger.exception("Unexpected error in exegol_exec")

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
        logger.error(f"Tool execution failed: {e.error_code}")

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


async def handle_exegol_status(
    cfg: Config, server_start_time: float = 0.0
) -> MCPResponse:
    """
    MCP tool handler for exegol_status.

    Returns server health status, configuration, and Exegol availability.

    Args:
        cfg: Configuration object
        server_start_time: Server start timestamp

    Returns:
        MCPResponse with ServerStatus data (always succeeds unless server broken)
    """
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
