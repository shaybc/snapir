"""Resolve only explicit fixture references; never infer or manufacture missing values."""
from copy import deepcopy
from models.fixture_reference import FixtureReference


def pointer(value, path):
    """Read a strict JSON pointer, preserving an explicit null and rejecting missing fields."""
    for token in path.split('/')[1:] if path else []:
        token=token.replace('~1','/').replace('~0','~')
        if isinstance(value,list):
            if not token.isdigit() or str(int(token))!=token:raise ValueError('Invalid fixture array index')
            try:value=value[int(token)]
            except IndexError as error:raise ValueError('Missing fixture array element') from error
        elif isinstance(value,dict) and token in value:value=value[token]
        else:raise ValueError('Missing fixture pointer: '+path)
    return value


def resolve(bank, reference, active=()):
    """Return a fresh logical value; cyclic or missing fixture references are errors."""
    ref=reference if isinstance(reference,FixtureReference) else FixtureReference.model_validate(reference)
    if ref.fixture_id in active:raise ValueError('Cyclic fixture reference: '+ref.fixture_id)
    if ref.fixture_id not in bank.fixtures:raise ValueError('Missing fixture: '+ref.fixture_id)
    def visit(value):
        if isinstance(value,dict):
            if '$fixture' in value:
                if set(value)-{'$fixture','pointer'}:raise ValueError('Malformed nested fixture reference')
                return resolve(bank,dict(fixture_id=value['$fixture'],pointer=value.get('pointer','')),(*active,ref.fixture_id))
            return {key:visit(child) for key,child in value.items()}
        if isinstance(value,list):return [visit(child) for child in value]
        return deepcopy(value)
    return deepcopy(pointer(visit(bank.fixtures[ref.fixture_id].value),ref.pointer))
