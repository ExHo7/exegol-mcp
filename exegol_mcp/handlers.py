"""MCP tool handlers."""

import logging
from datetime import datetime, timezone
import time
from typing import Optional, Dict, Any

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
from .workflows import WorkflowManager, WorkflowCategory, WorkflowDifficulty

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


async def handle_list_workflows(
    category: Optional[str] = None,
    difficulty: Optional[str] = None,
    tags: Optional[list] = None,
) -> MCPResponse:
    """
    MCP tool handler for listing available workflows.

    Args:
        category: Optional category filter
        difficulty: Optional difficulty filter
        tags: Optional tags filter

    Returns:
        MCPResponse with workflows list
    """
    logger.info("MCP tool list_workflows invoked")

    try:
        # Convert string filters to enums if provided
        category_enum = WorkflowCategory(category) if category else None
        difficulty_enum = WorkflowDifficulty(difficulty) if difficulty else None

        # List workflows
        workflows = WorkflowManager.list_workflows(
            category=category_enum,
            difficulty=difficulty_enum,
            tags=tags,
        )

        # Convert to dict format
        workflows_data = [workflow.to_dict() for workflow in workflows]

        return MCPResponse(
            success=True,
            data={
                "workflows": workflows_data,
                "total_count": len(workflows),
            },
            metadata={
                "tool": "list_workflows",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )

    except Exception as e:
        logger.exception("Unexpected error in list_workflows")
        return MCPResponse(
            success=False,
            error=ErrorDetails(
                error_code="UNKNOWN_ERROR",
                message=str(e),
                details="An unexpected error occurred while listing workflows",
                remediation="Check server logs for details",
            ),
            metadata={
                "tool": "list_workflows",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )


async def handle_run_workflow(
    workflow_name: str,
    container_name: str,
    params: Dict[str, str],
    cfg: Config,
    session_manager: Optional[any] = None,
) -> MCPResponse:
    """
    MCP tool handler for running a predefined workflow.

    Args:
        workflow_name: Name of the workflow to run
        container_name: Exegol container to execute in
        params: Workflow parameters
        cfg: Configuration object
        session_manager: Optional SessionManager instance

    Returns:
        MCPResponse with workflow execution results
    """
    logger.info(f"MCP tool run_workflow invoked: {workflow_name}")

    try:
        # Get workflow
        workflow = WorkflowManager.get_workflow(workflow_name)
        if not workflow:
            return MCPResponse(
                success=False,
                error=ErrorDetails(
                    error_code="WORKFLOW_NOT_FOUND",
                    message=f"Workflow '{workflow_name}' not found",
                    details=f"The workflow '{workflow_name}' does not exist",
                    remediation="Use list_workflows to see available workflows",
                ),
                metadata={
                    "tool": "run_workflow",
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                },
            )

        # Validate parameters
        missing_params = WorkflowManager.validate_params(workflow, params)
        if missing_params:
            return MCPResponse(
                success=False,
                error=ErrorDetails(
                    error_code="MISSING_PARAMETERS",
                    message=f"Missing required parameters: {', '.join(missing_params)}",
                    details=f"Workflow '{workflow_name}' requires: {workflow.required_params}",
                    remediation=f"Provide all required parameters: {', '.join(missing_params)}",
                ),
                metadata={
                    "tool": "run_workflow",
                    "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
                },
            )

        # Execute workflow steps
        results = []
        for step in workflow.steps:
            try:
                # Render command with parameters
                command = step.render(params)

                logger.info(f"Executing step: {step.name}")

                # Execute command
                if cfg.use_persistent_sessions and session_manager:
                    result = await exec_via_session(
                        container_name, command, cfg, session_manager
                    )
                else:
                    result = await exec_exegol_command(container_name, command, cfg)

                results.append({
                    "step_name": step.name,
                    "description": step.description,
                    "command": command,
                    "success": result.exit_code == 0,
                    "exit_code": result.exit_code,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "execution_time_ms": result.execution_time_ms,
                })

                # Stop if step failed and continue_on_failure is False
                if result.exit_code != 0 and not step.continue_on_failure:
                    logger.warning(f"Step '{step.name}' failed, stopping workflow")
                    break

            except Exception as e:
                logger.error(f"Error executing step '{step.name}': {e}")
                results.append({
                    "step_name": step.name,
                    "description": step.description,
                    "command": step.command_template,
                    "success": False,
                    "error": str(e),
                })

                if not step.continue_on_failure:
                    break

        # Return results
        all_successful = all(r.get("success", False) for r in results)

        return MCPResponse(
            success=True,
            data={
                "workflow_name": workflow_name,
                "workflow_description": workflow.description,
                "container_name": container_name,
                "parameters": params,
                "steps_executed": len(results),
                "total_steps": len(workflow.steps),
                "all_successful": all_successful,
                "results": results,
            },
            metadata={
                "tool": "run_workflow",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )

    except Exception as e:
        logger.exception("Unexpected error in run_workflow")
        return MCPResponse(
            success=False,
            error=ErrorDetails(
                error_code="UNKNOWN_ERROR",
                message=str(e),
                details="An unexpected error occurred while running the workflow",
                remediation="Check server logs for details",
            ),
            metadata={
                "tool": "run_workflow",
                "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            },
        )
