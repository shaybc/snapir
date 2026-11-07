"""Discover persisted Status and Resume choices independently of usable migration configs."""

from pathlib import Path
import sqlite3

import yaml

import constants
from cli.discovery import RESUMABLE_PHASES, discover_configurations
from cli.gate_decisions import GATE_PHASES
from runtime.workspace_paths import resolve_run_directory, run_database_path
from cli.run_presentation import read_run_summary


def discover_run_roots(project: Path) -> list[Path]:
    """Resolve the default root and YAML output roots without validating migration inputs."""
    roots = {(project / constants.OUTPUT_ROOT).resolve()}
    try:
        configurations = discover_configurations(project)
    except OSError:
        configurations = []
    for configuration in configurations:
        try:
            data = yaml.safe_load(configuration.read_text(encoding="utf-8"))
            output_root = data.get("output_root") if isinstance(data, dict) else None
            if isinstance(output_root, str) and output_root.strip():
                roots.add((configuration.parent / output_root).resolve())
        except (OSError, ValueError, yaml.YAMLError):
            continue
    return sorted(roots)


def discover_status_runs(project: Path, *, resumable_only: bool = False,
                         awaiting_gate_only: bool = False) -> list[tuple[str, str]]:
    """List readable current-layout run databases using directory paths as selection identities."""
    runs = {}
    for root in discover_run_roots(project):
        try:
            directories = sorted(root.iterdir()) if root.is_dir() else []
        except OSError:
            continue
        for directory in directories:
            try:
                directory = resolve_run_directory(str(root), directory.name)
                database = run_database_path(directory)
                if not database.is_file():
                    continue
                summary = read_run_summary(directory)
                if (not resumable_only or (summary['phase'] in RESUMABLE_PHASES and
                                                  (directory / "state" / "profile.json").is_file())) and (
                        not awaiting_gate_only or summary['phase'] in GATE_PHASES):
                    runs[str(directory)] = summary
            except (OSError, ValueError, KeyError, sqlite3.Error):
                continue
    return [(path, summary['label']) for path, summary in
            sorted(runs.items(), key=lambda item: (item[1]['latest'], item[0]), reverse=True)]
