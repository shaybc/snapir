"""Select a pilot or report persisted outcomes; never start or approve a conversion."""
import argparse
import json
from pathlib import Path
import sqlite3
from tools.behavior_verification.pilot_selection import select_pilot
from tools.behavior_verification.pilot_measurement import measure_pilot


def main(argv=None):
    """Use existing preparation/boundary JSON and a read-only migration database."""
    parser=argparse.ArgumentParser(description=__doc__)
    commands=parser.add_subparsers(dest='command',required=True)
    select=commands.add_parser('select')
    select.add_argument('--preparation',required=True)
    select.add_argument('--boundaries',required=True)
    select.add_argument('--dataset-type',choices=['production','bank_demo'],required=True)
    select.add_argument('--per-group',type=int,default=20)
    select.add_argument('--output',required=True)
    report=commands.add_parser('report')
    for name in ('sample','database','run-id','run-output','output'): report.add_argument('--'+name,required=True)
    args=parser.parse_args(argv)
    load=lambda path:json.loads(Path(path).read_text(encoding='utf-8'))
    if args.command=='select':
        result=select_pilot(load(args.preparation),load(args.boundaries),dataset_type=args.dataset_type,per_group=args.per_group)
    else:
        conn=sqlite3.connect(Path(args.database).resolve().as_uri()+'?mode=ro',uri=True)
        conn.row_factory=sqlite3.Row
        try: result=measure_pilot(conn,load(args.sample),run_id=args.run_id,output_root=args.run_output)
        finally: conn.close()
    output=Path(args.output); output.parent.mkdir(parents=True,exist_ok=True)
    temporary=output.with_name(output.name+'.tmp')
    temporary.write_text(json.dumps(result,indent=2,ensure_ascii=True),encoding='utf-8'); temporary.replace(output)
    print(str(output.resolve()))
    return 0


if __name__=='__main__': raise SystemExit(main())
