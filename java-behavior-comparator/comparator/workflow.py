"""Deterministic staged review: inventory, mapping, comparison, reverse coverage and interactions."""
from pathlib import Path
import os
from comparator.models import digest, save, Incomplete
from comparator.configuration import ROOT
from comparator.input_catalog import catalog, unchanged
from comparator.source_index import index
from comparator.evidence import Evidence
from comparator.state import Tasks
from comparator.behavior_inventory import inventory
from comparator.counterpart_mapping import locate
from comparator.behavior_comparison import compare
from comparator.coverage_review import reverse
from comparator.interaction_review import review as review_interactions
from comparator.review_issues import ReviewIssues
from comparator.reporting import finish
from comparator.stage_contracts import BASE, text
from comparator import progress

BOUNDARY=BASE+"""Describe the proposed original/native API input, output, exception and context mapping.
The listed entries may differ structurally. Do not change semantics to make them agree. Unknown
mapping, missing versus null, aliasing and caller responsibilities must remain explicit uncertainties.
Return {"input_mapping":"...","output_mapping":"...","exception_mapping":"...",
"context_mapping":"...","uncertainties":["unresolved question"]}.
"""


def choose_targets(inputs,evidence):
    """Use explicit pairs or the sole target class on each side; never guess among multiple roots."""
    if inputs['targets']: return inputs['targets']
    choices={}
    for side in ('original','generated'):
        paths={item['path'] for item in inputs['sources'] if item['side']==side and item['target']}
        choices[side]=sorted(record['name'] for record in evidence.classes.values()
                             if record['side']==side and record['file'] in paths)
        if len(choices[side])!=1:
            raise ValueError('Select '+side+' target class explicitly. Candidates: '+', '.join(choices[side]))
    return [dict(original_class=choices['original'][0],generated_class=choices['generated'][0])]


def run(settings,request,output,ask=None):
    """Analyze immutable inputs; persist partial work and resume only matching evidence."""
    output=Path(output).resolve();inputs=catalog(request,output,settings);output.mkdir(parents=True,exist_ok=True)
    progress.protect_inputs(request)
    progress.update('analysis','indexing')
    lock=output/'.comparison.lock'
    try:
        descriptor=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    except FileExistsError:
        raise ValueError('Comparison output is already in use: '+str(output)) from None
    try:
        os.write(descriptor,str(os.getpid()).encode())
        return analyze(settings,request,output,inputs,ask)
    finally:
        os.close(descriptor);lock.unlink()


def analyze(settings,request,output,inputs,ask):
    """Run the controlled stages inside one locked output directory."""
    implementation=[*Path(__file__).parent.glob('*.py'),*sorted((ROOT/'indexer/src').rglob('*.java')),ROOT/'indexer/pom.xml']
    code_hash=digest({path.relative_to(ROOT).as_posix():path.read_text(encoding='utf-8') for path in implementation})
    settings=dict(settings,implementation_hash=code_hash)
    run_folder=output/'runs'/digest([inputs['input_hash'],settings])[:24];run_folder.mkdir(parents=True,exist_ok=True)
    save(run_folder/'inputs.json',inputs)
    indexed=index(inputs,settings,output)
    evidence=Evidence(indexed)
    targets=choose_targets(inputs,evidence)
    tasks=Tasks(settings,output/'cache',evidence.chunks,ask)
    results=[];issues=ReviewIssues();summaries=[];interaction_stats=[]
    for pair in targets:
        original=evidence.scope('original',pair['original_class'],request['original'].get('entry_methods',[]))
        generated=evidence.scope('generated',pair['generated_class'],request['generated'].get('entry_methods',[]))
        allowed=evidence.references(original)|evidence.references(generated)
        for gap in original['gaps']+generated['gaps']:
            issues.add(gap,category='source_gap')
        def boundary_schema(value):
            for key in ('input_mapping','output_mapping','exception_mapping','context_mapping'): text(value,key)
            if not isinstance(value.get('uncertainties'),list) or not all(isinstance(v,str) for v in value['uncertainties']):
                raise ValueError('uncertainties must list unresolved mapping questions')
        try:
            entry_original=[i for i in original['roots'] if evidence.chunks[i]['name'] in {'format','unformat'}][:2]
            entry_generated=[i for i in generated['roots'] if evidence.chunks[i]['name'] in {'format','unformat'}][:2]
            boundary=tasks.call('boundary',BOUNDARY,dict(target=pair,
                original_catalog=evidence.headers(original['roots']),generated_catalog=evidence.headers(generated['roots']),
                original_evidence=evidence.capsule(entry_original,original),
                generated_evidence=evidence.capsule(entry_generated,generated)),boundary_schema,allowed)
            for uncertainty in boundary['uncertainties']:
                issues.add(uncertainty,category='boundary_uncertainty',stage='boundary')
        except Incomplete as error:
            boundary=dict(uncertainties=[str(error)]);issues.failure(error,stage='boundary')
        behaviors=[];inventories={};mappings={};mapping_causes={};member_candidates={}
        for identity in original['ids']:
            try:
                found,receipt=inventory(tasks,evidence,identity,original)
                behaviors.extend(found);inventories[identity]=receipt
            except Incomplete as error: issues.failure(error,stage='inventory',reference=identity,source=identity)
        for behavior in behaviors:
            try:
                candidates=locate(tasks,evidence,behavior,original,generated,
                                  preferred=member_candidates.get(behavior['source'],()))
                mappings[behavior['id']]=candidates
            except Incomplete as error:
                mapping_causes[behavior['id']]=issues.failure(error,stage='mapping',reference=behavior['id'],source=behavior['source'])
                continue
            if not candidates:
                mapping_causes[behavior['id']]=issues.add('No generated counterpart identified for '+behavior['description'],
                    category='unmapped_behavior',stage='mapping',reference=behavior['id'],source=behavior['source'])
                continue
            member_candidates.setdefault(behavior['source'],set()).update(candidates)
            try:
                value=compare(tasks,evidence,[behavior],candidates,original,generated,boundary)
                if boundary['uncertainties'] and value['verdict']=='difference':
                    value=dict(value,verdict='inconclusive',explanation='Input/API mapping is unresolved: '+value['explanation'])
                results.append(dict(value,behaviors=[behavior['id']],target=pair))
            except Incomplete as error: issues.failure(error,stage='compare',reference=behavior['id'],source=behavior['source'])
        coverage={}
        for identity in generated['ids']:
            try:
                covered=reverse(tasks,evidence,identity,behaviors,original,generated)
                coverage[identity]=covered
                if covered['status'] in {'uncertain','extra_suspected'}:
                    issues.add(covered['reason'],category='generated_coverage',
                               stage='coverage',reference=identity,source=identity,side='generated')
            except Incomplete as error: issues.failure(error,stage='coverage',reference=identity)
        interaction_stats.append(review_interactions(tasks,evidence,behaviors,mappings,mapping_causes,
                                 original,generated,boundary,pair,issues,results))
        summaries.append(dict(target=pair,original_scope=original,generated_scope=generated,
                              behaviors=behaviors,inventory=inventories,mappings=mappings,generated_coverage=coverage))
    if not unchanged(inputs['files']): raise ValueError('Inspected input files changed during comparison')
    roots=issues.summary()
    budgets=tasks.budget_summary()
    budgets['max_interaction_pairs']=dict(limit=settings['max_interaction_pairs'],scope='per_target',
        used=max((item['attempted'] for item in interaction_stats),default=0),
        exhausted=any(item['limit_exhausted'] for item in interaction_stats))
    usage=dict(budgets=budgets,calls_by_stage=tasks.calls_by_stage,interactions=interaction_stats,
        mapping_reuse=tasks.mapping_reuse,cache=dict(reused_receipts=len(tasks.cached_receipts),migrated_receipts=len(tasks.migrated_receipts)))
    save(run_folder/'analysis.json',dict(targets=summaries,results=results,issues=[item['message'] for item in issues.details],
        issue_details=issues.details,root_causes=roots,**usage))
    report=finish(inputs,targets,results,[item['message'] for item in roots],tasks.calls,indexed.get('warnings',[]),run_folder,
                  root_causes=roots,usage=usage)
    report['report_path']=str(run_folder/'report.json')
    report['configuration_hash']=digest(settings)
    report['implementation_hash']=code_hash
    report['model']=dict(provider=settings['model_provider'],name=settings['model_name'],endpoint_hash=digest(settings['model_base_url']))
    cited={identity for item in report['remarks'] for key in ('original_evidence','generated_evidence') for identity in item.get(key,[])}
    report['source_locations']={identity:{key:evidence.chunks[identity][key] for key in ('file','line','end_line','owner','signature')}
                                for identity in sorted(cited)}
    save(run_folder/'report.json',report)
    save(run_folder/'repair-feedback.json',dict(decision=report['decision'],evidence_level='static_analysis',
        remarks=report['remarks'],source_locations=report['source_locations'],root_causes=roots,**usage))
    progress.update('complete','finished',model_call=tasks.calls)
    return report
