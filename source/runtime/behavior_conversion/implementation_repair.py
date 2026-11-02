"""Describe focused implementation repairs using retained candidate and compile evidence."""
from copy import deepcopy
import json
import re
from models.native_implementation import NativeImplementation
from runtime.behavior_conversion.response_json import clean_structural_escapes
from runtime.managed_conversion_response import _remove_response_fence
from tools.component_inventory_tools.identity import stable_id


def repair_baseline(implementation, compiled):
    """Return exact retained Java and only the validation claims supported by its hash."""
    if not implementation.get('artifact_json') or not compiled.get('artifact_json'):
        return None
    candidate=json.loads(implementation['artifact_json'])
    proof=json.loads(compiled['artifact_json'])
    if (stable_id(candidate)!=implementation.get('artifact_hash') or stable_id(proof)!=compiled.get('artifact_hash')
            or proof.get('production_hash')!=stable_id(candidate) or not proof.get('validation',{}).get('build_passed')):
        return None
    NativeImplementation.model_validate(candidate)
    return dict(candidate=candidate,candidate_hash=stable_id(candidate),compile_hash=compiled['artifact_hash'],
        passed_checks=['production_compilation'],acceptance=False,
        instruction='Use this last compiled candidate as the repair baseline; behavioral acceptance is not established.')


def focused_repair(request, baseline):
    """Keep exact feedback while adding source locations and a narrow repair instruction."""
    feedback=request.get('implementation_feedback') or {}
    error=request.get('correction_feedback') or feedback.get('error')
    if not error:
        return request
    result=deepcopy(request)
    candidate=None
    try:
        raw=request.get('previous_model_response') or ''
        candidate=NativeImplementation.model_validate_json(clean_structural_escapes(_remove_response_fence(raw))).model_dump(mode='json')
    except ValueError:
        pass
    sources=(candidate or (baseline or {}).get('candidate') or feedback.get('previous_implementation') or {}).get('files',[])
    signature=re.search(r'not generic state: (.+?)\. Derive fields',str(error))
    locations=[]
    if signature:
        method=signature.group(1)
        from runtime.behavior_conversion.method_contracts import _signature,java_type_resolver
        for file in sources:
            resolve=java_type_resolver(file['content'],())
            expected=_signature(method,resolve)
            declarations=re.findall(r'\bpublic\s+[^{};]*?\([^()]*\)',file['content'])
            if expected and any(_signature(declaration,resolve)==expected for declaration in declarations):
                locations.append(dict(file=file['path'],method=method))
    for diagnostic in request.get('compiler_correction',{}).get('diagnostics',[]):
        locations.append({key:diagnostic[key] for key in ('file','line','column','message') if key in diagnostic})
    if not locations:
        locations=[dict(file=file['path']) for file in sources if file['path'] in str(error)]
    result['implementation_repair']=dict(defect=str(error),locations=locations,
        instruction='Fix only the reported defect and necessary callers. Preserve unaffected behavior, accepted APIs, IBM-free code and specific boundary types; do not broadly regenerate the implementation. Return complete corrected files.')
    if baseline:
        result['implementation_repair']['baseline']=deepcopy(baseline)
    else:
        result['implementation_repair']['baseline_status']='No hash-matched compiled candidate is available; the previous reply is failed evidence, not validated code.'
    return result
