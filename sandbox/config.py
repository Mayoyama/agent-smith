"""Sandbox configuration loading and default values."""

from common import SandboxConfig
from pydantic import ValidationError
import sys


def get_default_config() -> SandboxConfig:
    """Build a SandboxConfig with the default values from the subject.

    Returns:
        SandboxConfig: Config with the default import allowlist, allowed
            directories, 30 s timeout and 512 MB memory limit.
    """

    authorized_imports: list[str] = [
        "math", "math.*",
        "collections", "collections.*",
        "itertools", "re", "json",
        "typing", "typing.*",
        "functools", "operator",
        "heapq", "bisect", "copy",
        "string", "random",
        "datetime", "datetime.*",
        "array", "cmath",
    ]

    allowed_directories: list[str] = [
        "/testbed",
        "/tmp/agent",
    ]

    max_execution_time_seconds: int = 30
    max_memory_mb: int = 512

    return SandboxConfig(
        authorized_imports=authorized_imports,
        allowed_directories=allowed_directories,
        max_execution_time_seconds=max_execution_time_seconds,
        max_memory_mb=max_memory_mb,
    )


def load_config_or_defaults(config_path: str | None = None) -> SandboxConfig:
    """Load the sandbox config from a JSON file, or use the defaults.

    Args:
        config_path: Path to a JSON config file. If None, the default config is
            returned.

    Returns:
        SandboxConfig: The validated config.

    Raises:
        SystemExit: If the file can't be read or its contents are invalid.
    """

    if config_path is None:
        return get_default_config()

    try:
        with open(config_path, "r") as f:
            config = SandboxConfig.model_validate_json(f.read())
            return config

    except (OSError, ValidationError) as e:
        print(f"Config error: {e}.\nExiting.", file=sys.stderr)
        sys.exit(1)
