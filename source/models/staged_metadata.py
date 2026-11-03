"""Metadata-only stage schemas derived from existing final bundle contracts."""
from copy import deepcopy
from functools import lru_cache
from pydantic import ConfigDict,create_model
from models.operation_data_contract import OperationDataContract


def _without_sources(model,name,excluded,overrides=None):
    fields={key:(field.annotation,deepcopy(field)) for key,field in model.model_fields.items() if key not in excluded}
    fields.update(overrides or {})
    return create_model(name,__config__=ConfigDict(extra='forbid'),**fields)


OperationContractMetadata=_without_sources(OperationDataContract,'OperationContractMetadata',{'sources'})


@lru_cache
def metadata_schema(schema,batched=False):
    """Remove code/tests/dependencies from the model's metadata response contract."""
    if schema is OperationDataContract:return OperationContractMetadata
    overrides={}
    excluded={'files','dependencies','coverage'}
    if batched:
        from models.metadata_checklist_batch import ComponentSemantics,UnitSemantics
        excluded.update({'checklist_implementations','checklist_answers','evidence_ids'})
        if 'contracts' in schema.model_fields:overrides['contracts']=(dict[str,ComponentSemantics],...)
        if 'unit_contract' in schema.model_fields:overrides['unit_contract']=(UnitSemantics | None,None)
    if 'operation_contract' in schema.model_fields:
        overrides['operation_contract']=(OperationContractMetadata | None,None)
    return _without_sources(schema,schema.__name__.replace('Bundle','Semantics' if batched else 'Metadata'),excluded,overrides)


@lru_cache
def deterministic_metadata_schema(schema,conversion_only=False):
    """Ask only for interpretation; application code supplies API ownership and identities."""
    from models.metadata_checklist_batch import ComponentSemantics
    base=metadata_schema(schema,True)
    excluded={'unit_contract','behavior_implementations'}
    if conversion_only:excluded.add('verification_binding')
    overrides={}
    if conversion_only and 'unit_contract' in schema.model_fields:
        overrides['entry_type']=(str | None,None)
    if 'contracts' in schema.model_fields:
        excluded.add('contracts')
        details=_without_sources(ComponentSemantics,'ComponentDetails',{'api_types','api_members'})
        overrides['component_details']=(details,...)
    return _without_sources(base,schema.__name__.replace('Bundle','Details'),excluded,overrides)
