"""Revalidate saved production code while refusing implementation generation or correction."""
from models.native_implementation import NativeImplementation
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
from tools.component_inventory_tools.identity import stable_id


def revalidate_frozen(value,expected_hash,check):
    """Compile a verified copy without trusting an old successful build receipt."""
    production=NativeImplementation.model_validate(value.model_dump(mode='json')).model_copy(deep=True)
    if stable_id(production.model_dump(mode='json'))!=expected_hash:
        raise VerificationIncomplete(dict(stage='frozen_implementation_integrity',errors=['Saved production hash changed']))
    check(production)
    if stable_id(production.model_dump(mode='json'))!=expected_hash:
        raise VerificationIncomplete(dict(stage='frozen_implementation_integrity',errors=['Production changed during revalidation']))
    return production


def refuse_production_change(validator,error):
    """A required Java correction is a stop condition for a frozen continuation."""
    if getattr(validator,'frozen_implementation',None) is not None:
        raise VerificationIncomplete(dict(stage='frozen_implementation_requires_change',errors=[str(error)],
            implementation_regeneration_allowed=False,details=getattr(error,'verification_feedback',None))) from error
