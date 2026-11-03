"""Apply shared pins to generation, builds and coordinated saved-candidate revalidation."""
import json
from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from models.maven_dependency import MavenDependency
from models.shared_dependency_policy import SharedDependencyPolicy
from tools.conversion_tools.scoped_reuse.fingerprints import digest
from tools.state_store_tools import dependency_locks

_active=ContextVar('shared_dependency_policy',default=None)


def load_policy(profile):
    """Read only an explicitly configured, versioned dependency policy."""
    path=getattr(profile,'dependency_policy_path',None)
    policy=SharedDependencyPolicy.model_validate_json(Path(path).read_text(encoding='utf-8')) if path else None
    session=_active.get()
    if policy is not None and session and digest(policy.model_dump(mode='json'))!=session[2]:
        raise ValueError('Shared dependency policy changed during generation')
    return policy


def versions(policy):
    """Expose approved per-artifact versions, preserving BOM patch-version differences."""
    return {**policy.managed_versions,**{item.group_id+':'+item.artifact_id:item.version for item in policy.dependencies}} if policy else {}


def canonical_dependencies(profile,values,*,historical=False):
    """Rebind trusted historical build inputs; reject conflicting new AI proposals."""
    policy=load_policy(profile)
    if policy is None:return [value.model_copy(deep=True) if isinstance(value,MavenDependency) else MavenDependency.model_validate(value) for value in values]
    approved=versions(policy);result={}
    for value in values:
        item=value.model_copy(deep=True) if isinstance(value,MavenDependency) else MavenDependency.model_validate(value)
        coordinate=item.group_id+':'+item.artifact_id;expected=approved.get(coordinate)
        if expected and item.version!=expected:
            if not historical:raise ValueError('Shared dependency policy requires '+coordinate+':'+expected+', proposed '+item.version)
            item=item.model_copy(update={'version':expected})
        key=(item.group_id,item.artifact_id)
        previous=result.get(key)
        if previous and (previous.version,previous.scope)!=(item.version,item.scope):raise ValueError('Conflicting dependency pins: '+coordinate)
        if previous:item.required_classes=sorted(set(previous.required_classes+item.required_classes))
        result[key]=item
    return list(result.values())


def inventory(profile,known=()):
    """Supply shared class ownership and every approved version to each independent request."""
    policy=load_policy(profile)
    if policy is None:return list(known)
    hints={(item.group_id,item.artifact_id):item for item in policy.dependencies}
    session=_active.get()
    if session:
        for value in dependency_locks.read(session[0],session[1],session[2]):
            item=MavenDependency.model_validate(value);hints.setdefault((item.group_id,item.artifact_id),item)
    for coordinate,version in versions(policy).items():
        group,artifact=coordinate.split(':');hints.setdefault((group,artifact),MavenDependency(group_id=group,artifact_id=artifact,version=version,reason='Approved shared dependency policy'))
    merged={key:item.model_copy(deep=True) for key,item in hints.items()}
    for item in canonical_dependencies(profile,known,historical=True):
        key=(item.group_id,item.artifact_id);prior=merged.get(key)
        if prior and prior.version!=item.version:raise ValueError('Shared dependency lock conflict: '+item.group_id+':'+item.artifact_id)
        if prior:item.required_classes=sorted(set(prior.required_classes+item.required_classes))
        merged[key]=item
    return [item.model_dump(mode='json') for _,item in sorted(merged.items())]


@contextmanager
def dependency_policy_scope(conn,run_id,profile,payload):
    """Share verified choices across generations while leaving unconfigured runs unchanged."""
    policy=load_policy(profile)
    if policy is None:
        yield;return
    token=_active.set((conn,run_id,digest(policy.model_dump(mode='json')),profile))
    try:
        payload['known_dependencies']=inventory(profile,payload.get('known_dependencies',[]))
        payload['shared_dependency_policy']=digest(policy.model_dump(mode='json'))
        yield
    finally:_active.reset(token)


def import_owner(imp,candidates):
    """Use verified class ownership only inside an explicitly enabled shared-policy generation."""
    session=_active.get()
    if session is None:return None
    from tools.maven_dependency_tools.import_ownership import verified_import_owner
    return verified_import_owner(session[3],imp,candidates)


def check_resolved(profile,dependencies,*,remember=False):
    """Validate actual resolved graphs, and retain choices only after a successful build."""
    if load_policy(profile) is None:return
    pins=canonical_dependencies(profile,dependencies)
    session=_active.get()
    if session:
        locked={(item['group_id'],item['artifact_id']):item['version'] for item in dependency_locks.read(session[0],session[1],session[2])}
        for item in pins:
            if locked.get((item.group_id,item.artifact_id),item.version)!=item.version:raise ValueError('Resolved dependency conflicts with shared lock: '+item.coordinates)
        if remember:dependency_locks.remember(session[0],session[1],session[2],pins)
