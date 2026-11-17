"""Standalone command/menu orchestration; no migration runtime or state is imported."""
import argparse
import sys
from pathlib import Path
from format_library.configuration import TOOL_ROOT, load_config
from format_library.files import read_json, write_json


def discover(config, rebuild=False):
    """Persist and print the dependency-first catalog."""
    from format_library.discovery import scan
    from format_library.planning import build_plan
    plan = build_plan(scan(config, build=rebuild))
    write_json(Path(config['output_root']) / 'plan.json', plan)
    from format_library.discovery_reporting import record_plan, print_summary
    record_plan(plan)
    print_summary(plan)
    return plan


def status(config):
    """Show prepared candidates, blockers and approval availability without analysis or generation."""
    root = Path(config['output_root'])
    paths = sorted([*(root / 'foundations').glob('*/component.json'), *(root / 'components').glob('*/component.json')])
    from format_library.foundation_planning import POLICY, verify_selection
    from format_library.workspaces import verify_inputs
    from format_library.approval import collect_prerequisites
    for path in paths:
        item = read_json(path)
        latest = path.parent / 'latest.json'
        state = 'blocked' if item['blockers'] else 'prepared'
        if latest.is_file():
            state = 'generated candidate'
        if item.get('policy') != POLICY:
            state = 'legacy preparation: rediscover required'
        elif not item['blockers']:
            try:
                verify_inputs(path.parent, item)
                verify_selection(config, item)
                prerequisites = collect_prerequisites(config, path.parent, item, copy_files=False)
                if latest.is_file():
                    candidate = read_json(path.parent / read_json(latest)['candidate'] / 'candidate.json')
                    if [(value['id'], value['revision']) for value in prerequisites] != [
                            (value['id'], value['revision']) for value in candidate['prerequisites']]:
                        state = 'stale candidate: prerequisite approvals changed'
                else:
                    state = 'ready for conversion'
            except (ValueError, OSError, KeyError) as error:
                state += '; blocked prerequisite: ' + str(error)
        attempts = sorted((path.parent / 'attempts').glob('*/result.json'), key=lambda value: value.stat().st_mtime_ns)
        if attempts:
            state += '; latest attempt: ' + read_json(attempts[-1])['status']
        print(item.get('stage', 'legacy').upper() + ' ' + ', '.join(item['members']) + ': ' + state + '\n  ' + str(path.parent))
    index = Path(config['approved_library_root']) / 'index.json'
    if index.is_file():
        print('Approved group revisions: ' + str(len(read_json(index))))


def menu(config):
    """Offer deliberate local actions; never start AI conversion during discovery or preparation."""
    from format_library.workspaces import prepare
    from format_library.model_client import convert
    from format_library.approval import approve
    while True:
        print('\nFormat library tool\n1. Discover and plan\n2. Prepare folders\n3. Show status\n'
              '4. Convert a prepared folder\n5. Approve reviewed code\n0. Exit')
        action = input('Choice: ').strip()
        if action == '0':
            return
        try:
            if action == '1':
                discover(config)
            elif action == '2':
                plan_path = Path(config['output_root']) / 'plan.json'
                plan = read_json(plan_path) if plan_path.is_file() else discover(config)
                for item in plan['groups']:
                    print(item.get('stage', 'legacy') + ': ' + item.get('name', item['id']) + ' | ' + ', '.join(item['members']))
                stage = input('Stage: foundation, component, or all (default all): ').strip() or 'all'
                if stage not in {'foundation', 'component', 'all'}:
                    raise ValueError('Unknown preparation stage')
                names = [name.strip() for name in input('Exact/unique short names, comma separated (empty = all): ').split(',') if name.strip()]
                for folder in prepare(config, plan, names, stage=stage):
                    print('Prepared: ' + str(folder))
            elif action == '3':
                status(config)
            elif action == '4':
                result = convert(config, input('Prepared component folder: ').strip().strip('"'))
                print('Generated: ' + str(result) if result else 'AI reported blocked; see attempts')
            elif action == '5':
                folder = input('Prepared component folder: ').strip().strip('"')
                if input('Type APPROVE after reviewing its latest generated code: ').strip() == 'APPROVE':
                    print('Approved: ' + str(approve(config, folder, reviewed=True)))
        except (ValueError, OSError, KeyError) as error:
            print('Cannot complete: ' + str(error))


def main(argv=None):
    """Parse CLI actions; an argument-free launch opens the interactive menu."""
    parser = argparse.ArgumentParser(description='Prepare and generate a reviewed native format library independently of migration')
    parser.add_argument('--config', default=str(TOOL_ROOT / 'config.yaml'))
    commands = parser.add_subparsers(dest='command')
    scanning = commands.add_parser('discover')
    scanning.add_argument('--rebuild-scanner', action='store_true')
    preparing = commands.add_parser('prepare')
    preparing.add_argument('--select', action='append', default=[])
    preparing.add_argument('--stage', choices=['foundation', 'component', 'all'], default='all')
    for name in ('convert', 'approve'):
        action = commands.add_parser(name)
        action.add_argument('--folder', required=True)
        if name == 'approve':
            action.add_argument('--reviewed', action='store_true')
    commands.add_parser('status')
    args = parser.parse_args(argv)
    try:
        config = load_config(args.config)
        if args.command == 'discover':
            discover(config, args.rebuild_scanner)
        elif args.command == 'prepare':
            from format_library.workspaces import prepare
            path = Path(config['output_root']) / 'plan.json'
            plan = read_json(path) if path.is_file() else discover(config)
            for folder in prepare(config, plan, args.select, stage=args.stage):
                print('Prepared: ' + str(folder))
        elif args.command == 'convert':
            from format_library.model_client import convert
            result = convert(config, args.folder)
            print('Generated candidate: ' + str(result) if result else 'AI reported blocked; see attempts')
        elif args.command == 'approve':
            from format_library.approval import approve
            print('Approved: ' + str(approve(config, args.folder, reviewed=args.reviewed)))
        elif args.command == 'status':
            status(config)
        else:
            menu(config)
        return 0
    except (ValueError, OSError, KeyError) as error:
        print('Format library tool: ' + str(error), file=sys.stderr)
        return 1
    except (KeyboardInterrupt, EOFError):
        print('\nCancelled; existing files are retained.')
        return 130


if __name__ == '__main__':
    raise SystemExit(main())
