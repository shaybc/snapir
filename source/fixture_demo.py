"""Prepare optional operation demo references without starting conversion or any server."""
import argparse
import json
from runtime.fixture_demo.preparation import prepare_operation_demo, PINNED_BUNDLE


def main():
    """Use saved scenario references and a caller-pinned installed tool bundle."""
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project',required=True)
    parser.add_argument('--output-root',required=True)
    parser.add_argument('--operation',required=True)
    parser.add_argument('--bundle',default=PINNED_BUNDLE)
    parser.add_argument('--port',type=int,default=15432)
    parser.add_argument('--generate-scenarios',action='store_true')
    parser.add_argument('--profile',help='Saved converter model/check settings; credentials stay in the environment')
    parser.add_argument('--state-db',help='Optional saved conversion database, opened read-only for original evidence')
    parser.add_argument('--run-id')
    parser.add_argument('--source-root',help='Original Composer source root when --state-db is supplied')
    parser.add_argument('--verify',action='store_true',help='Explicitly build/test and execute the selected scenario using saved Java')
    args=parser.parse_args()
    profile=None;generation=None
    if args.generate_scenarios or args.verify:
        if not args.profile:parser.error('--profile is required for generation/verification')
        from pathlib import Path
        from models.pipeline_configuration import PipelineConfiguration
        profile=PipelineConfiguration.model_validate_json(Path(args.profile).read_text(encoding='utf-8'))
    if args.generate_scenarios:
        original=None
        if args.state_db:
            if not args.source_root:parser.error('--source-root is required with --state-db')
            from runtime.fixture_demo.scenario_evidence import read_saved_operation
            original=read_saved_operation(args.state_db,args.operation,args.source_root,args.run_id)
        from runtime.fixture_demo.scenario_generation import generate_operation_scenarios
        generation=generate_operation_scenarios(args.project,args.operation,profile,original=original)
    report=prepare_operation_demo(args.project,args.output_root,args.operation,bundle_id=args.bundle,port=args.port,
        generation_issue=('; '.join(generation['issues']) if generation and generation['status']!='prepared' else None))
    if generation:report['scenario_generation']=generation
    if args.verify and report['status']=='prepared':
        from runtime.fixture_demo.scenario_verification import verify_operation_scenario
        report['verification']=verify_operation_scenario(args.project,args.operation,profile)
    print(json.dumps(report,indent=2))
    if (args.generate_scenarios and report['status']!='prepared') or (args.verify and
            report.get('verification',{}).get('status')!='verified_against_prepared_expectations'):
        raise SystemExit(1)


if __name__=='__main__':main()
