"""Synthetic CLI protocol peer for format-library tests; not a behavior-review implementation."""
import hashlib
import json
from pathlib import Path
import sys


def digest(value): return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
args=sys.argv[1:]
request=json.loads(Path(args[args.index('--request')+1]).read_text(encoding='utf-8'))
files={}
for side in ('original','generated'):
    for key in ('sources','dependency_sources','jars'):
        for value in request[side].get(key,[]):
            root=Path(value)
            for path in sorted(root.rglob('*')) if root.is_dir() else [root]:
                if path.is_file(): files[str(path.resolve())]=hashlib.sha256(path.read_bytes()).hexdigest()
identity=dict(files=files,targets=request['targets'],encodings={side:request[side].get('encoding','UTF-8') for side in ('original','generated')},
              entry_methods={side:request[side].get('entry_methods',[]) for side in ('original','generated')})
config=json.loads(Path(args[args.index('--config')+1]).read_text(encoding='utf-8'))
decision=config.get('decision','consistent_in_review')
report=dict(schema_version='java-behavior-comparison-v1',tool_version='test-peer',decision=decision,complete=decision=='consistent_in_review',
    evidence_level='static_analysis',input_hash=digest(identity),files=files,targets=request['targets'],
    findings=[],remarks=[] if decision=='consistent_in_review' else [dict(message='Synthetic difference',suggested_action='Restore original behavior')])
if config.get('stale'): report['files']={}
for key in ('root_causes','budgets','calls_by_stage','interactions','mapping_reuse','cache'):
    if key in config: report[key]=config[key]
print(json.dumps(report));raise SystemExit(dict(consistent_in_review=0,differences_found=1,inconclusive=2,error=3)[decision])
