"""Standalone CLI/JSON entry point, with no imports from the converter or other tools."""
import argparse
import json
import os
from pathlib import Path
import sys
from comparator.configuration import ROOT, load
from comparator.models import SCHEMA, VERSION, DECISIONS, save
from comparator.input_catalog import catalog
from comparator.source_index import index
from comparator.workflow import run


class Arguments(argparse.ArgumentParser):
    """Keep invalid invocations machine-readable too."""
    def error(self,message): raise ValueError(message)


def resolve_request(value,base):
    """Resolve generic input paths relative to their request file, not another tool's config."""
    for side in ('original','generated'):
        if not isinstance(value.get(side),dict): continue
        for key in ('sources','dependency_sources','jars'):
            if isinstance(value[side].get(key,[]),list):
                value[side][key]=[str((base/Path(item)).resolve()) for item in value[side].get(key,[])]
    return value


def main(argv=None):
    """Emit one JSON result and a decision exit code; operational diagnostics use stderr."""
    parser=Arguments(description='Read-only staged original/native Java behavior comparison')
    parser.add_argument('command',choices=['compare','index'],nargs='?',default='compare')
    parser.add_argument('--config',default=str(ROOT/'config.yaml'))
    parser.add_argument('--request')
    parser.add_argument('--output',default=str(ROOT/'work'))
    parser.add_argument('--original');parser.add_argument('--generated')
    parser.add_argument('--original-class');parser.add_argument('--generated-class')
    parser.add_argument('--original-encoding',default='UTF-8');parser.add_argument('--generated-encoding',default='UTF-8')
    for side in ('original','generated'):
        parser.add_argument('--'+side+'-source',action='append',default=[])
        parser.add_argument('--'+side+'-jar',action='append',default=[])
    try:
        args=parser.parse_args(argv);settings=load(args.config)
        if args.request:
            request_path=Path(args.request).resolve()
            request=resolve_request(json.loads(request_path.read_text(encoding='utf-8-sig')),request_path.parent)
        else:
            if not args.original or not args.generated: raise ValueError('Supply --request or both --original and --generated')
            if bool(args.original_class)!=bool(args.generated_class): raise ValueError('Supply both target class names when selecting targets')
            request=dict(schema_version='java-behavior-comparison-request-v1',targets=[])
            for side in ('original','generated'):
                request[side]=dict(sources=[getattr(args,side)],dependency_sources=getattr(args,side+'_source'),
                                   jars=getattr(args,side+'_jar'),encoding=getattr(args,side+'_encoding'))
            if args.original_class:
                request['targets']=[dict(original_class=args.original_class,generated_class=args.generated_class)]
            request=resolve_request(request,Path.cwd())
        if args.command=='index':
            output=Path(args.output).resolve();inputs=catalog(request,output,settings);output.mkdir(parents=True,exist_ok=True)
            result=index(inputs,settings,output);save(output/'catalog.json',result)
            print(json.dumps(dict(schema_version=SCHEMA,decision='indexed',catalog=str(output/'catalog.json'),
                                  classes=sorted(result['classes']),warnings=result['warnings'])))
            return 0
        if not settings['model_name'] or 'REPLACE' in settings['model_name'] or not settings['model_base_url']:
            raise ValueError('Configure the independent comparator model_name/model_base_url')
        if not os.environ.get(settings['model_api_key_environment']):
            raise ValueError('Set comparator API-key environment variable: '+settings['model_api_key_environment'])
        report=run(settings,request,args.output)
        print(json.dumps(report));return DECISIONS[report['decision']]
    except Exception as error:
        report=dict(schema_version=SCHEMA,tool_version=VERSION,decision='error',complete=False,evidence_level='static_analysis',
                    error=str(error),remarks=[dict(message=str(error),suggested_action='Correct comparator inputs/configuration; no code was approved.')])
        print(json.dumps(report));return DECISIONS['error']


if __name__=='__main__': raise SystemExit(main())
