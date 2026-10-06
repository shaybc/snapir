"""Command-line entry point for starting and inspecting migration runs."""

import argparse
import json
import sqlite3
import uuid

from runtime.configuration import load_configuration
from runtime.pipeline_runner import run_pipeline
from runtime.checkpoints import resume_pipeline
from runtime.human_gates import record_decision
from runtime.workspace_paths import resolve_run_directory
from tools.state_store_tools.runs import get_run


def main(argv: list[str] | None = None) -> int:
    """Start intake or display persisted run status, returning a process exit code."""
    parser = argparse.ArgumentParser(description="Run generic Composer migration intake through planning inputs.")
    parser.add_argument("command", choices=["start", "status", "resume", "approve", "reject"])
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-id")
    parser.add_argument("--gate", type=int, choices=range(1, 5))
    args = parser.parse_args(argv)
    try:
        profile = load_configuration(args.config)
        if args.command == "start":
            directory = run_pipeline(profile, args.run_id or f"run-{uuid.uuid4().hex}")
            print(f"Run workspace: {directory}")
            print("Intake stopped before model-driven planning. Inspect status for the persisted result.")
        elif args.command == "resume":
            if not args.run_id:
                parser.error("resume requires --run-id")
            print(f"Run workspace: {resume_pipeline(profile.output_root, args.run_id)}")
        elif args.command in {"approve", "reject"}:
            if not args.run_id or not args.gate:
                parser.error("approval commands require --run-id and --gate")
            directory = resolve_run_directory(profile.output_root, args.run_id)
            report = (directory / f"gate_{args.gate}_report.txt").read_text(encoding="utf-8")
            database = directory / "migration.db"
            with sqlite3.connect(database.as_uri() + "?mode=rw", uri=True) as conn:
                run = conn.execute("SELECT current_phase FROM runs WHERE run_id=?", (args.run_id,)).fetchone()
                if run is None or run[0] not in {f"gate_{args.gate}_pending", f"gate_{args.gate}_rejected"}:
                    raise ValueError("Run is not waiting at this gate")
                record_decision(conn, args.run_id, args.gate, report,
                                "approved" if args.command == "approve" else "rejected")
            print("Decision recorded. Resume the run to continue.")
        else:
            if not args.run_id:
                parser.error("status requires --run-id")
            database = resolve_run_directory(profile.output_root, args.run_id) / "migration.db"
            with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as conn:
                conn.row_factory = sqlite3.Row
                run = get_run(conn, args.run_id)
                if run is None:
                    raise ValueError("Run not found")
                print(json.dumps({key: run[key] for key in ("run_id", "status", "current_phase")}, indent=2))
        return 0
    except (ValueError, OSError, RuntimeError, sqlite3.Error) as exc:
        print(f"Migration error: {exc}")
        return 1
