"""Delegate narrow stage calls to an already-authorized original conversion task."""
from contextvars import ContextVar
from contextlib import contextmanager

_stage=ContextVar('authorized_conversion_stage',default=None)
_recovery=ContextVar('authorized_conversion_recovery',default=None)


def verify_parent(conn,config,profile,category,identity,payload):
    """Recheck the unchanged source/checkpoint scope; no stage creates authorization."""
    recovery=_recovery.get()
    if recovery and recovery[0] is conn and recovery[1] is config and recovery[2] is profile and recovery[3:5]==(category,identity):
        return recovery[5]()
    if category=='component_generation':
        from runtime.component_conversion.scope import require_component_task
        return require_component_task(conn,config,profile,identity,payload)
    else:
        from tools.conversion_tools.scoped_workflow.preparation import is_scoped_run
        if is_scoped_run(conn,config.run_id):
            from runtime.scoped_native.scope import require_task
            return require_task(conn,config,profile,category,identity,payload)


@contextmanager
def authorized_recovery(conn,config,profile,category,identity,verify):
    """Bind one bounded baseline/simplification to its authorized original task."""
    verify()
    token=_recovery.set((conn,config,profile,category,identity,verify))
    try:yield
    finally:_recovery.reset(token)


@contextmanager
def authorized_stage(conn,config,settings,category,identity,verify):
    """Bind one internal stage to its original task before any result lookup/model call."""
    verify()
    token=_stage.set((conn,config,settings,category,identity,verify))
    try:yield
    finally:_stage.reset(token)


def verify_stage(conn,config,profile,category,identity):
    """Only an exact application-created child may use its parent's checkpoint proof."""
    current=_stage.get()
    if current is None:return False
    if current[0] is not conn or current[1] is not config or current[2] is not profile or current[3:5]!=(category,identity):
        raise ValueError('Staged task does not match its authorized parent')
    current[5]()
    return True
