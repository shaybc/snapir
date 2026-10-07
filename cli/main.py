"""Command-line entry point for starting and inspecting migration runs."""

import argparse
import json
import sqlite3
import traceback
import uuid

from runtime.configuration import load_configuration
from runtime.pipeline_runner import run_pipeline
from runtime.checkpoints import resume_pipeline
from runtime.human_gates import record_decision
from runtime.workspace_paths import resolve_run_directory, run_database_path
from tools.state_store_tools.runs import get_run
from cli.interactive import SelectionCancelled, complete_arguments, complete_run_selection
from cli.diagnostics import console_diagnostics
from cli.readme import open_readme
from cli.configuration_wizard import create_configuration


def main(argv: list[str] | None = None) -> int:
    """Start intake or display persisted run status, returning a process exit code."""
    parser = argparse.ArgumentParser(description="Run generic Composer migration intake through planning inputs.")
    parser.add_argument("command", nargs="?", choices=["start", "status", "resume", "approve", "reject"])
    parser.add_argument("--config")
    parser.add_argument("--run-id")
    parser.add_argument("--gate", type=int, choices=range(1, 5))
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Show exception stack traces and debug diagnostic logs.")
    args = parser.parse_args(argv)
    diagnostics = console_diagnostics(args.verbose)
    diagnostics.__enter__()
    try:
        while True:
            complete_arguments(args, parser)
            if args.command == "create_config":
                create_configuration()
            elif args.command == "help":
                parser.print_help()
            elif args.command == "readme":
                open_readme()
            else:
                break
            args.command = None
        if args.command == "exit":
            return 0
        profile = load_configuration(args.config)
        if args.command in {"approve", "reject"} and not args.gate:
            parser.error("approval commands require --run-id and --gate")
        complete_run_selection(args, profile)
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
            database = run_database_path(directory)
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
            database = run_database_path(resolve_run_directory(profile.output_root, args.run_id))
            with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as conn:
                conn.row_factory = sqlite3.Row
                run = get_run(conn, args.run_id)
                if run is None:
                    raise ValueError("Run not found")
                print(json.dumps({key: run[key] for key in ("run_id", "status", "current_phase")}, indent=2))
        return 0
    except SelectionCancelled:
        print("Selection cancelled.")
        return 130
    except (ValueError, OSError, RuntimeError, sqlite3.Error) as exc:
        print(f"Migration error: {exc}")
        if args.verbose:
            traceback.print_exc()
        return 1
    finally:
        diagnostics.__exit__(None, None, None)
