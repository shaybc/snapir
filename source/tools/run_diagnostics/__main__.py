"""Select an existing migration for offline, read-only diagnosis."""

from pathlib import Path
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
    print('\n'.join(diagnose(directory)))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, EOFError):
        print('Diagnostic could not read the selected run. Check the folder and try again.')
        sys.exit(1)
