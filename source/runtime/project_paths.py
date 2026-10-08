"""Locate application source and project data independently of the working directory."""

from pathlib import Path


def source_root() -> Path:
    """Return the directory containing the application packages."""
    return Path(__file__).resolve().parents[1]


def project_root() -> Path:
    """Return the project directory containing configs, documentation, and work data."""
    return source_root().parent
