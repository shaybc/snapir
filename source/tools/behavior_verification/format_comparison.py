"""Explicit standalone format diagnostics; does not invoke or resume the converter."""
import argparse
import json
import os
from pathlib import Path
import tempfile
from models.format_comparison_plan import FormatComparisonPlan
from models.pipeline_configuration import PipelineConfiguration
from runtime.format_comparison.context_discovery import discover_context
from runtime.format_comparison.runner import run_comparison


def main(argv=None):
    """Load a declarative plan and optional AI discovery; write diagnostics in a fresh directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', required=True)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--output')
    parser.add_argument('--enable', action='store_true', help='Explicitly permit original/native diagnostic execution')
    parser.add_argument('--discover-context', action='store_true', help='Make a bounded AI context-discovery request')
    parser.add_argument('--no-facts', action='store_true', help='Skip fact collection and fact-derived probes for this comparison test only')
    parser.add_argument('--windows-user-key', action='store_true', help='Load the configured model key from Windows user environment')
    args = parser.parse_args(argv)
    plan = FormatComparisonPlan.model_validate_json(Path(args.plan).read_text(encoding='utf-8'))
    profile = PipelineConfiguration.model_validate_json(Path(args.profile).read_text(encoding='utf-8'))
    if not args.enable:
        parser.error('Explicit --enable is required; this command executes original code')
    profile.format_comparison.enabled = True
    if args.no_facts:
        profile.format_comparison.collect_facts = False
    directory = Path(args.output) if args.output else Path(tempfile.mkdtemp(prefix='snapir-format-diagnostic-'))
    directory.mkdir(parents=True, exist_ok=True)
    if any(directory.iterdir()):
        parser.error('Output must be a new empty directory')
    if args.discover_context:
        from runtime.model_execution.adk_executor import AdkExecutor
        if args.windows_user_key:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, 'Environment') as environment:
                os.environ[profile.model_api_key_environment] = winreg.QueryValueEx(environment, profile.model_api_key_environment)[0]
        plan.discovery = discover_context(plan.original_unit, AdkExecutor(profile).execute,
                                          profile.format_comparison, directory / 'discovery',
                                          directions=sorted({entry.direction for entry in plan.entries.values()}))
    report = run_comparison(plan, profile, directory / 'execution')
    print(json.dumps(dict(status=report['status'], counts=report['counts'], report=str(directory / 'execution/format-comparison.json'))))
    return 0 if report['status'] == 'completed' and not any(report['counts'][key] for key in ('different', 'comparison_unavailable', 'execution_failed', 'unexecuted')) else 1


if __name__ == '__main__':
    raise SystemExit(main())
