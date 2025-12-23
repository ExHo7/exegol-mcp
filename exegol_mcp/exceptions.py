"""Custom exceptions for Exegol MCP."""


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
