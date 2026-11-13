"""Print a metadata-only format trace; run with python -m tools.run_diagnostics.trace_format_flow."""
import argparse
import json
import sys

from tools.run_diagnostics.format_flow_trace import extract_format_flow


def main():
    """Keep the migration untouched and print only whitelisted evidence metadata."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, help='Existing migration run directory')
    parser.add_argument('--diagnostics', help='Existing exported diagnostics directory, if separate from run')
    selector = parser.add_mutually_exclusive_group()
    selector.add_argument('--class', dest='implementation', help='Trace all groups for one implementation class')
    selector.add_argument('--group', help='Trace one exact component/group identity shown in diagnostics')
    args = parser.parse_args()
    try:
        implementation = args.implementation or (None if args.group else 'com.ibm.il.dse.cc.format.CCString')
        result = extract_format_flow(args.run, implementation, args.diagnostics, group_id=args.group)
    except Exception as error:
        print('Trace could not be completed (' + type(error).__name__ + '). No raw error content exported.', file=sys.stderr)
        return 1
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
