"""
Session Manager for Persistent Exegol Shells

This module provides a session manager for maintaining persistent shell sessions
in Exegol containers, avoiding the overhead of creating new processes for each command.
"""

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from typing import Dict, Optional

# ============================================================================
# DATA MODELS
# ============================================================================


@dataclass
class SessionConfig:
    """Configuration for Exegol sessions."""

    exegol_path: str
    default_timeout: int = 180
    session_idle_timeout: int = 300  # Close session after 5 minutes of inactivity
    output_marker_prefix: str = "__EXEGOL_MCP_END_"


@dataclass
class SessionMetrics:
    """Metrics for a session."""

    commands_executed: int = 0
    total_execution_time_ms: int = 0
    created_at: float = field(default_factory=time.time)
    last_command_at: float = field(default_factory=time.time)

    def record_command(self, execution_time_ms: int) -> None:
        """Record metrics for a command execution."""
        self.commands_executed += 1
        self.total_execution_time_ms += execution_time_ms
        self.last_command_at = time.time()

    def get_idle_time(self) -> float:
        """Get idle time in seconds since last command."""
        return time.time() - self.last_command_at

    def get_uptime(self) -> float:
        """Get session uptime in seconds."""
        return time.time() - self.created_at


# ============================================================================
# EXEGOL SESSION
# ============================================================================


class ExegolSession:
    """Maintain persistent shell session in Exegol container."""

    def __init__(self, container_name: str, config: SessionConfig):
        """
        Initialize a persistent Exegol session.

        Args:
            container_name: Name of the Exegol container
            config: Session configuration
        """
        self.container_name = container_name
        self.config = config
        self.session_id = str(uuid.uuid4())[:8]
        self.process: Optional[asyncio.subprocess.Process] = None
        self.metrics = SessionMetrics()
        self.logger = logging.getLogger(f"exegol_mcp.session.{self.session_id}")
        self._lock = asyncio.Lock()  # Prevent concurrent command execution
        self._is_closed = False

    async def start(self) -> None:
        """Start persistent bash session in Exegol container.

        Raises:
            RuntimeError: If session is already started or closed
            FileNotFoundError: If Exegol CLI is not found
        """
        if self.process is not None:
            raise RuntimeError(f"Session {self.session_id} is already started")

        if self._is_closed:
            raise RuntimeError(f"Session {self.session_id} is closed and cannot be restarted")

        self.logger.info(
            f"Starting persistent session for container '{self.container_name}'"
        )

        # Build Exegol exec command with interactive bash
        exegol_cmd = [
            self.config.exegol_path,
            "exec",
            "-v",
            self.container_name,
            "/bin/bash",
            "-i",  # Interactive mode
        ]

        try:
            self.process = await asyncio.create_subprocess_exec(
                *exegol_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            # Wait a bit for shell to initialize
            await asyncio.sleep(0.1)

            # Clear any initial output (shell prompt, etc.)
            await self._drain_initial_output()

            self.logger.info(
                f"Session {self.session_id} started successfully for container '{self.container_name}'"
            )

        except FileNotFoundError:
            self.logger.error(f"Exegol CLI not found at '{self.config.exegol_path}'")
            raise

    async def _drain_initial_output(self, timeout: float = 0.5) -> None:
        """Drain any initial output from the shell (prompts, welcome messages, etc.)."""
        if not self.process or not self.process.stdout:
            return

        try:
            # Read available output with short timeout
            while True:
                try:
                    await asyncio.wait_for(
                        self.process.stdout.read(4096), timeout=0.05
                    )
                except asyncio.TimeoutError:
                    break
        except Exception:
            pass

    async def exec(self, command: str, timeout: Optional[int] = None) -> Dict[str, any]:
        """
        Execute command in persistent session.

        Args:
            command: Command to execute
            timeout: Command timeout in seconds (uses default if None)

        Returns:
            Dictionary with stdout, stderr, exit_code, execution_time_ms

        Raises:
            RuntimeError: If session is not started or closed
            asyncio.TimeoutError: If command exceeds timeout
        """
        if self.process is None:
            raise RuntimeError(
                f"Session {self.session_id} is not started. Call start() first."
            )

        if self._is_closed:
            raise RuntimeError(f"Session {self.session_id} is closed")

        # Use lock to prevent concurrent command execution
        async with self._lock:
            return await self._exec_locked(command, timeout)

    async def _exec_locked(
        self, command: str, timeout: Optional[int] = None
    ) -> Dict[str, any]:
        """Internal method to execute command (must be called with lock held)."""
        if timeout is None:
            timeout = self.config.default_timeout

        start_time = time.time()
        marker = f"{self.config.output_marker_prefix}{uuid.uuid4().hex[:8]}"

        self.logger.debug(f"Executing command: {command}")

        # Construct command with exit code capture and output marker
        # Using PIPESTATUS to capture the actual command exit code, not echo's
        full_command = f"{command}\necho __EXEGOL_EXIT_CODE__$?\necho {marker}\n"

        # Send command
        if not self.process or not self.process.stdin:
            raise RuntimeError("Session stdin is not available")

        self.process.stdin.write(full_command.encode())
        await self.process.stdin.drain()

        # Collect output until marker
        stdout_lines = []
        exit_code = 0
        timed_out = False

        try:
            while True:
                if time.time() - start_time > timeout:
                    timed_out = True
                    self.logger.warning(
                        f"Command timed out after {timeout}s: {command}"
                    )
                    break

                try:
                    line = await asyncio.wait_for(
                        self.process.stdout.readline(), timeout=1.0
                    )
                except asyncio.TimeoutError:
                    # No output available, check if we've exceeded total timeout
                    continue

                if not line:
                    # Process ended
                    self.logger.error("Session process ended unexpectedly")
                    self._is_closed = True
                    raise RuntimeError("Session process ended unexpectedly")

                line_str = line.decode("utf-8", errors="replace")

                # Check for end marker
                if marker in line_str:
                    break

                # Check for exit code marker
                if line_str.startswith("__EXEGOL_EXIT_CODE__"):
                    try:
                        exit_code = int(line_str.replace("__EXEGOL_EXIT_CODE__", "").strip())
                    except ValueError:
                        exit_code = -1
                    continue

                stdout_lines.append(line_str)

        except Exception as e:
            self.logger.exception(f"Error during command execution: {e}")
            raise

        execution_time_ms = int((time.time() - start_time) * 1000)
        stdout = "".join(stdout_lines)

        # Update metrics
        self.metrics.record_command(execution_time_ms)

        self.logger.debug(
            f"Command completed in {execution_time_ms}ms with exit code {exit_code}"
        )

        return {
            "stdout": stdout,
            "stderr": "",  # stderr is harder to capture in interactive session
            "exit_code": exit_code if not timed_out else -1,
            "execution_time_ms": execution_time_ms,
            "timed_out": timed_out,
            "session_id": self.session_id,
        }

    async def close(self) -> None:
        """Close persistent session."""
        if self._is_closed:
            return

        self.logger.info(
            f"Closing session {self.session_id} "
            f"(executed {self.metrics.commands_executed} commands, "
            f"uptime: {self.metrics.get_uptime():.1f}s)"
        )

        if self.process:
            try:
                # Try graceful exit first
                if self.process.stdin:
                    self.process.stdin.write(b"exit\n")
                    await self.process.stdin.drain()

                # Wait for process to end (with timeout)
                try:
                    await asyncio.wait_for(self.process.wait(), timeout=2.0)
                except asyncio.TimeoutError:
                    # Force kill if graceful exit fails
                    self.process.kill()
                    await self.process.wait()

            except Exception as e:
                self.logger.error(f"Error during session close: {e}")
                if self.process:
                    self.process.kill()

        self._is_closed = True
        self.process = None

    def is_idle(self) -> bool:
        """Check if session has been idle too long."""
        return self.metrics.get_idle_time() > self.config.session_idle_timeout

    def get_info(self) -> Dict[str, any]:
        """Get session information."""
        return {
            "session_id": self.session_id,
            "container_name": self.container_name,
            "is_active": self.process is not None and not self._is_closed,
            "metrics": {
                "commands_executed": self.metrics.commands_executed,
                "total_execution_time_ms": self.metrics.total_execution_time_ms,
                "uptime_seconds": self.metrics.get_uptime(),
                "idle_time_seconds": self.metrics.get_idle_time(),
            },
        }


# ============================================================================
# SESSION MANAGER
# ============================================================================


class SessionManager:
    """Manage multiple persistent Exegol sessions."""

    def __init__(self, config: SessionConfig):
        """Initialize session manager.

        Args:
            config: Session configuration
        """
        self.config = config
        self.sessions: Dict[str, ExegolSession] = {}
        self.logger = logging.getLogger("exegol_mcp.session_manager")
        self._cleanup_task: Optional[asyncio.Task] = None

    async def get_or_create_session(self, container_name: str) -> ExegolSession:
        """Get existing session or create new one for container.

        Args:
            container_name: Name of the Exegol container

        Returns:
            ExegolSession instance (started and ready)
        """
        # Check if we already have a session for this container
        if container_name in self.sessions:
            session = self.sessions[container_name]
            if session.process and not session._is_closed:
                self.logger.debug(
                    f"Reusing existing session {session.session_id} for '{container_name}'"
                )
                return session
            else:
                # Session is dead, remove it
                self.logger.warning(
                    f"Removing dead session for '{container_name}'"
                )
                del self.sessions[container_name]

        # Create new session
        self.logger.info(f"Creating new session for container '{container_name}'")
        session = ExegolSession(container_name, self.config)
        await session.start()
        self.sessions[container_name] = session

        return session

    async def close_session(self, container_name: str) -> bool:
        """Close session for specific container.

        Args:
            container_name: Name of the container

        Returns:
            True if session was closed, False if no session existed
        """
        if container_name in self.sessions:
            session = self.sessions[container_name]
            await session.close()
            del self.sessions[container_name]
            return True
        return False

    async def close_all_sessions(self) -> None:
        """Close all active sessions."""
        self.logger.info(f"Closing all sessions ({len(self.sessions)} active)")

        for session in list(self.sessions.values()):
            await session.close()

        self.sessions.clear()

    async def cleanup_idle_sessions(self) -> int:
        """Close sessions that have been idle too long.

        Returns:
            Number of sessions closed
        """
        closed_count = 0
        containers_to_close = []

        for container_name, session in self.sessions.items():
            if session.is_idle():
                containers_to_close.append(container_name)

        for container_name in containers_to_close:
            self.logger.info(
                f"Closing idle session for '{container_name}' "
                f"(idle: {self.sessions[container_name].metrics.get_idle_time():.1f}s)"
            )
            await self.close_session(container_name)
            closed_count += 1

        return closed_count

    def get_all_sessions_info(self) -> Dict[str, any]:
        """Get information about all sessions."""
        return {
            "total_sessions": len(self.sessions),
            "sessions": {
                container: session.get_info()
                for container, session in self.sessions.items()
            },
        }

    async def start_cleanup_task(self, interval: int = 60) -> None:
        """Start background task to cleanup idle sessions.

        Args:
            interval: Cleanup interval in seconds
        """
        if self._cleanup_task and not self._cleanup_task.done():
            self.logger.warning("Cleanup task already running")
            return

        async def cleanup_loop():
            while True:
                try:
                    await asyncio.sleep(interval)
                    closed = await self.cleanup_idle_sessions()
                    if closed > 0:
                        self.logger.info(f"Cleanup task closed {closed} idle sessions")
                except asyncio.CancelledError:
                    break
                except Exception as e:
                    self.logger.error(f"Error in cleanup task: {e}")

        self._cleanup_task = asyncio.create_task(cleanup_loop())
        self.logger.info(f"Started cleanup task (interval: {interval}s)")

    async def stop_cleanup_task(self) -> None:
        """Stop background cleanup task."""
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
            self.logger.info("Stopped cleanup task")
