"""Diagnose saved migration state and export captured oversized request materials."""

from pathlib import Path
import sqlite3
import sys

from tools.run_diagnostics.report import diagnose


def main():
    """Accept a run-folder argument or offer a numbered list of existing run folders."""
    if len(sys.argv) > 1:
        directory = Path(sys.argv[1].strip('"'))
    else:
        project = Path(__file__).resolve().parents[3]
        try:
            from cli.status_discovery import discover_run_roots
            roots = discover_run_roots(project)
        except ImportError:
            roots = [project / 'work/migration_runs']
        runs = sorted({folder for root in roots if root.is_dir()
                       for folder in root.iterdir() if (folder / 'state/migration.db').is_file()},
                      key=lambda path: (path / 'state/migration.db').stat().st_mtime, reverse=True)
        print('Select a saved run (Enter selects the latest):')
        for number, run in enumerate(runs, 1):
            print(f'{number}. {run.name}')
        if runs:
            choice = input('Run number, full run folder, or Q to cancel: ').strip()
            if choice.lower() == 'q':
                return
            if not choice or choice.isdigit():
                index = int(choice or '1') - 1
                if index < 0 or index >= len(runs):
                    raise ValueError('Run number is outside the displayed list')
                directory = runs[index]
            else:
                directory = Path(choice.strip('"'))
        else:
            directory = Path(input('No runs found. Paste the full existing run folder: ').strip().strip('"'))
    from tools.run_diagnostics.ai_attempt_evidence import snapshot
    from tools.run_diagnostics.conversion_ai import is_conversion_phase, build_report, format_report
    from tools.run_diagnostics.conversion_ai_export import export_conversion_report
    from tools.run_diagnostics.html_report import export_html_report
    try:
        evidence = snapshot(Path(directory).resolve(), include_attempts=False)
    except (OSError, ValueError, sqlite3.Error):
        print('\n'.join(diagnose(directory)))
        return
    if is_conversion_phase(evidence['run']['current_phase']):
        report = build_report(directory)
        print('\n'.join(format_report(report)))
        print('\n'.join(export_conversion_report(directory, Path(__file__).resolve().parents[3], report)))
        print('\n'.join(export_html_report(directory, Path(__file__).resolve().parents[3], conversion=True)))
        return
    else:
        lines = diagnose(directory)
        print('\n'.join(lines))
        print('\n'.join(export_html_report(directory, Path(__file__).resolve().parents[3], diagnostic_lines=lines)))
        if not str(evidence['run']['current_phase'] or '').startswith(('conversion_', 'closure', 'dependency_closure')):
            return
    from tools.run_diagnostics.request_materials import export_request_materials
    print('\n'.join(export_request_materials(directory, Path(__file__).resolve().parents[3])))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, EOFError, sqlite3.Error):
        print('Diagnostic could not read the selected run. Check the folder and try again.')
        sys.exit(1)
