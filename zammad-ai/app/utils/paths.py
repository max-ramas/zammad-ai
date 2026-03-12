"""Utilities for resolving package-relative paths."""

from pathlib import Path


def get_prompts_dir() -> Path:
    """Get the prompts directory path relative to the package.

    Resolves the prompts directory path based on the package structure,
    ensuring it works regardless of the current working directory.

    Returns:
        Path: The absolute path to the prompts directory
    """
    return Path(__file__).resolve().parents[2] / "prompts"
