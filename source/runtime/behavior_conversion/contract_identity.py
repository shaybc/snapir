"""Compare only the data/API contracts that a configured unit actually exposes."""

import re
from tools.component_inventory_tools.identity import stable_id


def unit_contract_sources(contract, sources):
    """Select only types referenced by a unit's API, including their recursive fields."""
    remaining = {item["path"]: item["content"] for item in sources}
    selected = {}
    text = " ".join(api.type_name + " " + " ".join(api.method_signatures) for api in contract.apis)
    while True:
        matches = [name for name in remaining if re.search(r"\b" + re.escape(name.rsplit("/", 1)[-1][:-5]) + r"\b", text)]
        if not matches:
            break
        for name in matches:
            selected[name] = remaining.pop(name)
            text += "\n" + selected[name]
    return [dict(path=name, content=content) for name, content in sorted(selected.items())]


def unit_contract_identity(contract, sources):
    """Exclude unrelated operation DTOs from the public compatibility identity."""
    return stable_id([api.model_dump(mode="json") for api in contract.apis], contract.dependency_units,
                     unit_contract_sources(contract, sources))
