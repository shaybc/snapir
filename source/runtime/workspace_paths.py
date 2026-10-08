"""Resolve isolated output locations for a migration run."""

import re
from pathlib import Path


def resolve_run_directory(output_root: str, run_id: str) -> Path:
    """Return a contained run directory, rejecting path-like run identifiers."""
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", run_id):
        raise ValueError("run_id must contain only letters, numbers, underscores, or hyphens")
    root = Path(output_root).resolve()
    directory = (root / run_id).resolve()
    if not directory.is_relative_to(root):
        raise ValueError("run directory must stay within output_root")
    return directory


def run_database_path(directory: Path) -> Path:
    """Return the continuation database location within a resolved run directory."""
    return directory / "state" / "migration.db"


def run_profile_path(directory: Path) -> Path:
    """Return the continuation profile location within a resolved run directory."""
    return directory / "state" / "profile.json"


def run_report_path(directory: Path, filename: str) -> Path:
    """Return the report location in its README workflow stage."""
    from runtime.workflow_stages import REPORT_STAGES, REPORT_FOLDERS
    name = "dependency_closure.json" if filename == "closures.json" else filename
    return Path(directory) / "reports" / REPORT_FOLDERS[REPORT_STAGES[filename]] / name


def write_run_report(directory: Path, filename: str, content: str) -> Path:
    """Write report evidence while creating its containing stage directory."""
    path = run_report_path(directory, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path


def run_mapper_log_path(directory: Path) -> Path:
    """Return the mapper log location within a resolved run directory."""
    return directory / "logs" / "mapper.log"
