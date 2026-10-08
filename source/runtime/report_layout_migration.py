"""Relocate existing reports while preserving decisions on unchanged review evidence."""

import hashlib
import json
from pathlib import Path
import sqlite3

from runtime.gate_one_reports import read_gate_one_reports
from runtime.workspace_paths import run_database_path, run_report_path
from runtime.workflow_stages import REPORT_STAGES, STAGES, REPORT_FOLDERS


def _old_gate_one_bundle(directory):
    """Read the former bundle exactly as it was bound to approval."""
    overview = directory / "gate_1_report.md"
    manifest = directory / "reports" / "gate_1" / "manifest.json"
    if not overview.is_file() or not manifest.is_file():
        return None
    contents = {"gate_1_report.md": overview.read_text(encoding="utf-8")}
    for relative in json.loads(manifest.read_text(encoding="utf-8")):
        path = (directory / relative).resolve()
        if not path.is_relative_to(directory / "reports" / "gate_1") or path.suffix != ".md":
            raise ValueError("Invalid legacy Gate One report path")
        contents[relative] = path.read_text(encoding="utf-8")
    return hashlib.sha256(json.dumps(contents, ensure_ascii=False, sort_keys=True).encode()).hexdigest()


def migrate_report_layout(directory):
    """Move only recognized reports, rejecting collisions and paths outside the run."""
    directory = Path(directory).resolve()
    old_hash = _old_gate_one_bundle(directory)
    moves = []
    for filename in REPORT_STAGES:
        destination = run_report_path(directory, filename)
        for source in (directory / filename, directory / "reports" / filename):
            if source.is_file():
                moves.append((source, destination))
    for source, destination in (
        (directory / "reports" / "gate_1", directory / "reports" / "2_migration_planning" / "gate_1"),
        (directory / "runtime_test_reports", directory / "reports" / "6_service_generation_and_validation" / "runtime_test_reports"),
    ):
        if source.is_dir():
            moves.append((source, destination))
    destinations = set()
    for source, destination in moves:
        if not source.resolve().is_relative_to(directory) or not destination.resolve().is_relative_to(directory):
            raise ValueError("Report move must remain inside its run folder")
        if destination.exists() or destination in destinations:
            raise ValueError("Report destination already exists: " + str(destination))
        destinations.add(destination)
    if not moves:
        return []
    for stage in REPORT_FOLDERS.values():
        (directory / "reports" / stage).mkdir(parents=True, exist_ok=True)
    for source, destination in moves:
        destination.parent.mkdir(parents=True, exist_ok=True)
        source.rename(destination)
    if old_hash:
        overview = run_report_path(directory, "gate_1_report.md")
        overview.write_text(overview.read_text(encoding="utf-8").replace("(reports/gate_1/", "(gate_1/"), encoding="utf-8")
        bundle = directory / "reports" / "2_migration_planning" / "gate_1"
        for operation in (bundle / "operations").glob("*.md"):
            operation.write_text(operation.read_text(encoding="utf-8").replace("(../../../gate_1_report.md)", "(../../gate_1_report.md)"), encoding="utf-8")
        shared = bundle / "shared_libraries.md"
        shared.write_text(shared.read_text(encoding="utf-8").replace("(../../gate_1_report.md)", "(../gate_1_report.md)"), encoding="utf-8")
        manifest = bundle / "manifest.json"
        paths = json.loads(manifest.read_text(encoding="utf-8"))
        manifest.write_text(json.dumps([path.replace("reports/gate_1/", "reports/2_migration_planning/gate_1/", 1) for path in paths], indent=2), encoding="utf-8")
        new_hash = hashlib.sha256(read_gate_one_reports(directory).encode()).hexdigest()
        database = run_database_path(directory)
        if database.is_file():
            with sqlite3.connect(database.as_uri() + "?mode=rw", uri=True) as conn:
                if conn.execute("SELECT 1 FROM sqlite_master WHERE name='runtime_gate_decisions'").fetchone():
                    # Preserve the original decision and timestamp as review history.
                    rows = conn.execute("SELECT decision,policy,decided_at FROM runtime_gate_decisions WHERE run_id=? AND gate_number=1 AND report_hash=?", (directory.name, old_hash)).fetchall()
                    for decision, policy, decided_at in rows:
                        conn.execute("INSERT OR IGNORE INTO runtime_gate_decisions VALUES(?,1,?,?,?,?)", (directory.name, new_hash, decision, policy, decided_at))
    return [str(destination.relative_to(directory)) for _, destination in moves]


def number_report_folders(directory):
    """Prefix existing stage folders and carry matching review decisions forward."""
    directory = Path(directory).resolve()
    reports = directory / "reports"
    old_stage = reports / "migration_planning"
    old_hash = None
    if (old_stage / "gate_1_report.md").is_file():
        contents = {"reports/migration_planning/gate_1_report.md": (old_stage / "gate_1_report.md").read_text(encoding="utf-8")}
        manifest = old_stage / "gate_1" / "manifest.json"
        for relative in json.loads(manifest.read_text(encoding="utf-8")):
            path = (directory / relative).resolve()
            if not path.is_relative_to(old_stage / "gate_1") or path.suffix != ".md":
                raise ValueError("Invalid Gate One report path")
            contents[relative] = path.read_text(encoding="utf-8")
        old_hash = hashlib.sha256(json.dumps(contents, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    moves = [(reports / stage, reports / folder) for stage, folder in REPORT_FOLDERS.items() if (reports / stage).is_dir()]
    for source, destination in moves:
        if not source.resolve().is_relative_to(directory) or not destination.resolve().is_relative_to(directory):
            raise ValueError("Report move must remain inside its run folder")
        if destination.exists():
            raise ValueError("Report destination already exists: " + str(destination))
    for source, destination in moves:
        source.rename(destination)
    if old_hash:
        manifest = reports / REPORT_FOLDERS["migration_planning"] / "gate_1" / "manifest.json"
        paths = json.loads(manifest.read_text(encoding="utf-8"))
        manifest.write_text(json.dumps([path.replace("reports/migration_planning/", "reports/2_migration_planning/", 1) for path in paths], indent=2), encoding="utf-8")
        new_hash = hashlib.sha256(read_gate_one_reports(directory).encode()).hexdigest()
        database = run_database_path(directory)
        if database.is_file():
            with sqlite3.connect(database.as_uri() + "?mode=rw", uri=True) as conn:
                if conn.execute("SELECT 1 FROM sqlite_master WHERE name='runtime_gate_decisions'").fetchone():
                    rows = conn.execute("SELECT decision,policy,decided_at FROM runtime_gate_decisions WHERE run_id=? AND gate_number=1 AND report_hash=?", (directory.name, old_hash)).fetchall()
                    for decision, policy, decided_at in rows:
                        conn.execute("INSERT OR IGNORE INTO runtime_gate_decisions VALUES(?,1,?,?,?,?)", (directory.name, new_hash, decision, policy, decided_at))
    return [destination.name for _, destination in moves]
