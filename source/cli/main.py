"""Command-line entry point for starting and inspecting migration runs."""

import argparse
import json
import sqlite3
import uuid

from runtime.configuration import load_configuration
from runtime.pipeline_runner import run_pipeline
from runtime.checkpoints import resume_pipeline
from runtime.workspace_paths import resolve_run_directory, run_database_path
from tools.state_store_tools.runs import get_run
from cli.interactive import SelectionCancelled, complete_arguments, complete_run_selection, select_status_run, select_resume_run, select_gate_run
from cli.diagnostics import console_diagnostics
from cli.readme import open_readme
from cli.configuration_wizard import create_configuration
from cli.terminal_display import clear_screen
from runtime.model_execution.error_details import sanitize_diagnostic, print_failure_traceback
from runtime.model_execution.readiness import intake_model_warning
from cli.gate_decisions import pending_gate_number, record_gate_decision
from cli.gate_report_menu import offer_gate_one_report, offer_dependency_closure_report
from runtime.workflow_stages import workflow_stage_label
from cli.workflow_progress import display_workflow_progress


def main(argv: list[str] | None = None) -> int:
    """Start intake or display persisted run status, returning a process exit code."""
    parser = argparse.ArgumentParser(description="Run generic Composer migration intake through planning inputs.")
    parser.add_argument("command", nargs="?", choices=["start", "status", "resume", "approve", "reject"])
    parser.add_argument("--config")
    parser.add_argument("--run-id")
    parser.add_argument('--connection-answers', help='JSON list of last-resort service/driver decisions for Resume')
    parser.add_argument("--gate", type=lambda value: 'plan' if value == 'plan' else int(value), choices=[1, 2, 3, 4, 'plan'])
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Enable detailed file diagnostics; keep console progress concise.")
    args = parser.parse_args(argv)
    diagnostics = console_diagnostics(args.verbose)
    diagnostics.__enter__()
    try:
        while True:
            directory = None
            command_selected_from_menu = args.command is None
            complete_arguments(args, parser)
            if args.command == "create_config":
                create_configuration()
            elif args.command == "help":
                parser.print_help()
            elif args.command == "readme":
                open_readme()
            elif args.command == "start":
                profile = load_configuration(args.config)
                complete_run_selection(args, profile)
                run_id = args.run_id or f"run-{uuid.uuid4().hex}"
                directory = run_pipeline(profile, run_id)
                if command_selected_from_menu:
                    print(f"Run created: {run_id}")
                    if getattr(profile, "model_provider", None) is not None:
                        warning = intake_model_warning(profile)
                        if warning:
                            print(warning)
                print(f"Run workspace: {directory}")
                print("Intake result is saved. Inspect status and the intake reports for the plan or any blockers."
                      if getattr(profile, 'conversion_strategy', None) == 'behavior_units' else
                      "Intake stopped before model-driven planning. Inspect status for the persisted result.")
                if not command_selected_from_menu:
                    return 0
                print("Review the conversion plan in the intake reports and approve it when required."
                      if getattr(profile, 'conversion_strategy', None) == 'behavior_units' else
                      "You may review the intake reports before continuing. Choose Resume a migration when ready to begin planning.")
                args.run_id = None
            elif args.command in {"approve", "reject"} and command_selected_from_menu:
                try:
                    directory = select_gate_run()
                    gate = args.gate or pending_gate_number(directory)
                    if gate is None:
                        raise ValueError("No gate awaiting a decision for this run")
                    decision = "approved" if args.command == "approve" else "rejected"
                    record_gate_decision(directory, directory.name, gate, decision)
                except (ValueError, OSError, RuntimeError, sqlite3.Error) as exc:
                    print(f"Migration error: {sanitize_diagnostic(str(exc))}")
                    if args.verbose:
                        print("Detailed diagnostics are saved in the run's logs folder.")
                else:
                    print(f"Gate {gate} {decision} for run: {directory.name}")
                    print("Decision recorded. Resume the run to continue.")
                args.run_id = None
                args.gate = None
            elif args.command == "resume" and command_selected_from_menu:
                try:
                    directory = select_resume_run()
                    from cli.service_connections import answer_connection_questions
                    from pathlib import Path
                    answers = json.loads(Path(args.connection_answers).read_text()) if args.connection_answers else None
                    answer_connection_questions(directory, answers=answers)
                    resumed_directory = resume_pipeline(str(directory.parent), directory.name)
                    database = run_database_path(directory)
                    with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as conn:
                        result = conn.execute("SELECT status, current_phase FROM runs WHERE run_id=?",
                                              (directory.name,)).fetchone()
                    if result is None:
                        raise ValueError("Run not found")
                except (ValueError, OSError, RuntimeError, sqlite3.Error) as exc:
                    print(f"Migration error: {sanitize_diagnostic(str(exc))}")
                    if args.verbose:
                        print("Detailed diagnostics are saved in the run's logs folder.")
                else:
                    print(f"Resume returned for run: {directory.name}")
                    print(f"Run workspace: {resumed_directory}")
                    print(f"Saved status: {result[0]}; checkpoint: {result[1] or 'No checkpoint'}")
                    print(f"Workflow stage: {workflow_stage_label(result[1])}")
                    print("Choose View run status to inspect the result and any review requirements.")
                    from tools.state_store_tools.operation_progress import active_operation, operation_directory
                    with sqlite3.connect(database.as_uri() + '?mode=ro', uri=True) as progress_conn:
                        progress_conn.row_factory = sqlite3.Row
                        current = active_operation(progress_conn, directory.name)
                    report_directory = operation_directory(directory, current['operation_key']) if current else directory
                    if result[0] == "paused" and result[1] == "gate_1_pending":
                        offer_gate_one_report(report_directory)
                    elif result[0] == "blocked" and result[1] == "closures_blocked":
                        offer_dependency_closure_report(report_directory)
                args.run_id = None
            elif args.command == "status":
                if command_selected_from_menu:
                    directory = select_status_run()
                    run_id = directory.name
                else:
                    profile = load_configuration(args.config)
                    complete_run_selection(args, profile)
                    if not args.run_id:
                        parser.error("status requires --run-id")
                    directory = resolve_run_directory(profile.output_root, args.run_id)
                    run_id = args.run_id
                database = run_database_path(directory)
                with sqlite3.connect(database.as_uri() + "?mode=ro", uri=True) as conn:
                    conn.row_factory = sqlite3.Row
                    run = get_run(conn, run_id)
                    if run is None:
                        raise ValueError("Run not found")
                    status = {key: run[key] for key in ("run_id", "status", "current_phase")}
                    status["workflow_stage"] = workflow_stage_label(run["current_phase"])
                    from tools.state_store_tools.operation_progress import progress_rows
                    progress = progress_rows(conn, run_id)
                    if progress:
                        status['operations'] = [{key: item[key] for key in ('operation_key', 'position', 'status', 'phase')}
                                                for item in progress]
                    print(json.dumps(status, indent=2))
                if not command_selected_from_menu:
                    return 0
                args.run_id = None
            else:
                break
            if command_selected_from_menu and directory is not None:
                display_workflow_progress(directory)
            args.command = None
        if args.command == "exit":
            return 0
        profile = load_configuration(args.config)
        if args.command in {"approve", "reject"} and not args.gate:
            parser.error("approval commands require --run-id and --gate")
        complete_run_selection(args, profile)
        if args.command == "resume":
            if not args.run_id:
                parser.error("resume requires --run-id")
            if args.connection_answers:
                directory = resolve_run_directory(profile.output_root, args.run_id)
                from cli.service_connections import answer_connection_questions
                from pathlib import Path
                answers = json.loads(Path(args.connection_answers).read_text())
                answer_connection_questions(directory, answers=answers)
            print(f"Run workspace: {resume_pipeline(profile.output_root, args.run_id)}")
        elif args.command in {"approve", "reject"}:
            if not args.run_id or not args.gate:
                parser.error("approval commands require --run-id and --gate")
            directory = resolve_run_directory(profile.output_root, args.run_id)
            record_gate_decision(directory, args.run_id, args.gate,
                                 "approved" if args.command == "approve" else "rejected")
            print("Decision recorded. Resume the run to continue.")
        return 0
    except SelectionCancelled:
        print("Selection cancelled.")
        return 130
    except (ValueError, OSError, RuntimeError, sqlite3.Error) as exc:
        print(f"Migration error: {sanitize_diagnostic(str(exc))}")
        if args.verbose:
            print("Detailed diagnostics are saved in the run's logs folder when a run was opened.")
        return 1
    finally:
        diagnostics.__exit__(None, None, None)
