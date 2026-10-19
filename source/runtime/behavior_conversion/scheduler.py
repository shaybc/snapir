"""Order compatible whole-unit tasks and build native dependency libraries first."""

from tools.component_inventory_tools.dependency_order import dependency_first_order


def ordered_units(units, contracts, assignments):
    """Topologically order bundle dependencies; prioritize shared tasks when possible."""
    by_id = {unit.unit_id: unit for unit in units}
    order = dependency_first_order(by_id, {key: item.dependency_units for key, item in contracts.items()})
    # Stable topological order already preserves dependencies; ready sets prefer shared IDs.
    pending, result = list(order), []
    while pending:
        ready = [key for key in pending if set(contracts[key].dependency_units).issubset({unit.unit_id for unit in result})]
        if not ready:
            raise ValueError("Native unit dependency cycle")
        key = min(ready, key=lambda value: (not bool(assignments[value]), value))
        result.append(by_id[key])
        pending.remove(key)
    return result
