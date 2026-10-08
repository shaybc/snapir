"""Offer the saved Gate One Markdown overview after interactive planning."""

import webbrowser
import os

from cli.interactive import SelectionCancelled, select_option
from runtime.workspace_paths import run_report_path


def offer_gate_one_report(directory):
    """Open the original Markdown in a browser or return to the main menu."""
    report = run_report_path(directory, "gate_1_report.md").resolve()
    print("Planning is ready for review. Review the Gate One report, then choose Approve a gate when ready.")
    _offer_report(report, "Gate One review", "Gate One", "Markdown",
                  "Gate One report opened in your browser. Review it, then choose Approve a gate or Reject a gate.")


def offer_dependency_closure_report(directory):
    """Offer the original JSON findings when dependency closure blocks a run."""
    report = run_report_path(directory, "dependency_closure.json").resolve()
    print("Dependency closure is blocked. Open the report and review its blocking_issues for the required fixes.")
    _offer_report(report, "Dependency closure findings", "dependency closure", "JSON",
                  "Dependency closure report opened in your default application. Review the blocking issues before resuming.",
                  default_application=True)


def _offer_report(report, title, label, file_type, opened_message, default_application=False):
    """Keep report-opening choices and browser failures within the interactive session."""
    if not report.is_file():
        print(f"The {label} {file_type} report is unavailable. Resume this run to regenerate it.")
        return
    try:
        selected = select_option(title, [
            ("open", f"Open {label} report" + ("" if default_application else " in browser")),
            ("back", "Return to main menu"),
        ], clear_after_selection=False)
    except SelectionCancelled:
        return
    if selected != "open":
        return
    try:
        if default_application and hasattr(os, "startfile"):
            os.startfile(str(report))
            opened = True
        else:
            opened = webbrowser.open(report.as_uri(), new=2)
    except (webbrowser.Error, OSError):
        opened = False
    if opened:
        print(opened_message)
    else:
        target = "default application" if default_application else "browser"
        print(f"Could not open the {target}. Open this {file_type} report manually: {report}")
