"""Configuration loading and management."""

from pathlib import Path
import yaml

from .models import Config
from .exceptions import ConfigurationError


def load_config(path: str = "config.yaml") -> Config:
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
    return Config(
        exegol_path=data.get("exegol", {}).get("path", "exegol"),
        command_timeout=data.get("timeout", {}).get("command_execution", 180),
        log_level=data.get("logging", {}).get("level", "INFO"),
        log_format=data.get("logging", {}).get("format", "json"),
        server_name=data.get("mcp", {}).get("server_name", "exegol-mcp-server"),
        server_version=data.get("mcp", {}).get("version", "0.1.0"),
        compact_mode=data.get("mcp", {}).get("compact_mode", False),
        use_persistent_sessions=data.get("sessions", {}).get("enabled", False),
        session_idle_timeout=data.get("sessions", {}).get("idle_timeout", 300),
        auto_parse_output=data.get("parsing", {}).get("auto_parse", False),
    )
