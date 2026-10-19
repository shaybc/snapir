"""Count distinct consumers and assign whole configured units using existing thresholds."""

from models.native_ownership_plan import NativeOwnershipPlan
from tools.component_inventory_tools.identity import stable_id


def expand_dependency_consumers(units, contracts):
    """Include indirect consumers when a complete unit is used inside another unit."""
    by_id = {unit.unit_id: unit for unit in units}
    changed = True
    while changed:
        changed = False
        for key, contract in contracts.items():
            for dependency in contract.dependency_units:
                target = by_id[dependency]
                consumers = sorted(set(target.consumers + by_id[key].consumers))
                if consumers != sorted(target.consumers):
                    target.consumers = consumers
                    changed = True


def plan_unit_ownership(units, profile, compatibility=None):
    """Group only evidence/configuration/API-compatible units; never individual tags."""
    groups = {}
    compatibility = compatibility or {}
    for unit in units:
        key = stable_id(unit.fingerprint, compatibility.get(unit.unit_id, ""))
        groups.setdefault(key, set()).update(unit.consumers)
    assignments, consumers = {}, {}
    for unit in units:
        owners = sorted(groups[stable_id(unit.fingerprint, compatibility.get(unit.unit_id, ""))])
        count = len(owners)
        library = None
        if count >= profile.shared_library_min_usage:
            library = "common-lib" if count > profile.broad_library_usage_threshold else "shared-" + stable_id(owners)[:12]
        assignments[unit.unit_id] = library
        consumers[unit.unit_id] = owners
    return NativeOwnershipPlan(assignments=assignments, consumers=consumers,
                               fingerprint=stable_id(assignments, consumers, compatibility))
