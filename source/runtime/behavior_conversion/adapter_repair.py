"""Retry only invocation plans while keeping production and passing tests independent."""
from runtime.behavior_conversion.failure_routing import AdapterRepairRequired,record_correction
from runtime.behavior_conversion.executable_adapters import resolve_adapter


def validate_with_adapter_repair(tasks,payload,production,inventory,bundle,validator,recheck):
    """Use the existing durable adapter-role budget, then rerun all affected checks."""
    repaired=False
    while True:
        try:return validator(bundle,cached=False)
        except AdapterRepairRequired as error:
            if repaired:record_correction(tasks,'adapter',error.verification_feedback)
            binding=resolve_adapter(tasks,payload,production,inventory,repair_feedback=error.verification_feedback)
            bundle.verification_binding=binding
            recheck(binding)
            from runtime.behavior_conversion.verification_ladder import active_verification
            session=active_verification()
            if session:session.static(bundle)
            repaired=True
