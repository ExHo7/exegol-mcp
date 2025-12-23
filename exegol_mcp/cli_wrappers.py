"""Wrappers for Exegol CLI commands."""

import asyncio
import logging
import time
from typing import List, Optional

from .models import Config, CommandExecution, Container
from .exceptions import (
    ExegolNotFoundError,
    ContainerNotFoundError,
    CommandTimeoutError,
)
from .utils import truncate_output

logger = logging.getLogger(__name__)


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
    logger.info(
        f"Executing command in container '{container_name}': {command}"
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

            logger.warning(
                f"Command execution timed out after {cfg.command_timeout}s"
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
            logger.error(f"Container '{container_name}' not found")
            raise ContainerNotFoundError(container_name)

        # Log result
        logger.info(
            f"Command completed in {execution_time}ms with exit code {exit_code}"
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
        logger.error(f"Exegol CLI not found at '{cfg.exegol_path}'")
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
            logger.warning(
                f"exegol info returned non-zero exit code: {exit_code}"
            )

        # Parse output lines to Container objects
        containers: List[Container] = []
        for line in stdout.split("\n"):
            container = Container.from_exegol_info(line)
            if container:
                containers.append(container)

        logger.info(f"Found {len(containers)} containers")

        return containers

    except FileNotFoundError:
        logger.error(f"Exegol CLI not found at '{cfg.exegol_path}'")
        raise ExegolNotFoundError(cfg.exegol_path)


async def check_exegol_version(cfg: Config) -> Optional[str]:
    """
    Check if Exegol CLI is available and get its version.

    Args:
        cfg: Configuration object with exegol path

    Returns:
        Version string if Exegol is available, None otherwise
    """
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

        logger.debug(f"Exegol version: {stdout}")

        return stdout if stdout else None

    except FileNotFoundError:
        logger.debug(f"Exegol CLI not found at '{cfg.exegol_path}'")
        return None


async def exec_via_session(
    container_name: str,
    command: str,
    cfg: Config,
    session_manager,
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
        session_manager: SessionManager instance
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
