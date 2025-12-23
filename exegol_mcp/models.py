"""Data models for Exegol MCP."""

from dataclasses import dataclass, field
from typing import Any, Dict, Optional


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
    auto_parse_output: bool = False

    def __post_init__(self) -> None:
        """Validate configuration values."""
        from .exceptions import ConfigurationError

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
