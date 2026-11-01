"""Compare observable values while reporting absent presence and partial state separately."""
from tools.behavior_verification.boundary_comparison import compare_boundary_observations


def observed_type(value):
    """Name losslessly observed scalar kinds; null supplies no type evidence."""
    if value is None:return None
    if isinstance(value,bool):return 'boolean'
    if isinstance(value,str):return 'string'
    if isinstance(value,int):return 'integer'
    if isinstance(value,float):return 'number'
    if isinstance(value,dict) and '$decimal' in value:return 'decimal'
    return 'unsupported'


def expected_types(observations, fields):
    """Use actual legacy boundary values rather than guessing types from XML tag names."""
    result={field['context_key']:set() for field in fields}
    for observation in observations:
        if observation.status!='completed':continue
        for key in result:
            kind=observed_type(observation.context.get(key))
            if kind:result[key].add(kind)
    return result


def compare_observable_case(legacy,native,mappings,*,xml_output=False,logging_diagnostics=None,partial_state_on_exception=False):
    """Never count an unobservable presence/partial-state difference as either equality or a code defect."""
    limitations=[]
    if legacy.status!='completed' or native.status!='completed':
        return [],[dict(kind='execution_incomplete',issues=legacy.issues+native.issues)]
    left,right=legacy.model_copy(deep=True),native.model_copy(deep=True)
    ignored=set()
    for item in mappings:
        key=item['context_key']
        if item['status']!='bound':
            ignored.add(key);limitations.append(dict(kind=item['status'],path=item['path'],context_key=key))
        elif not item['presence_observable']:
            limitations.append(dict(kind='presence_not_observable',path=item['path'],context_key=key))
            # Only compare the value when a legacy field is actually observable. Absent is not null.
            if key not in legacy.context:ignored.add(key)
    for key in ignored:
        left.context.pop(key,None);right.context.pop(key,None)
    if legacy.exception is not None and (legacy.writes or partial_state_on_exception and legacy.removals):
        limitations.append(dict(kind='partial_writes_not_compared',keys=[write['key'] for write in [*legacy.writes,*legacy.removals]]))
        left.context={};right.context={};left.writes=[];right.writes=[];left.removals=[];right.removals=[]
    elif limitations:
        # A getter/presence flag cannot establish original write-event ordering or counts.
        left.writes=[];right.writes=[]
    return compare_boundary_observations(left,right,xml_output=xml_output,logging_diagnostics=logging_diagnostics),limitations
