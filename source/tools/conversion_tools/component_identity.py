"""Bind component reuse to current source/configuration, platform and explicit policy revisions."""
from models.component_conversion_plan import ComponentConversionPlan
from tools.conversion_tools.scoped_reuse.fingerprints import digest,conversion_policy

COMPONENT_POLICY_VERSION='component-contracts-format-step-v2'


def checked_plan(value):
    """Verify the exact CF1 plan before using its component/group bindings."""
    plan=ComponentConversionPlan.model_validate(value)
    if plan.fingerprint!=digest(plan.model_dump(mode='json',exclude={'fingerprint'})):
        raise ValueError('Component plan fingerprint does not match its contents')
    members=[member for group in plan.groups for member in group.members]
    if len(members)!=len(set(members)) or set(members)!=set(plan.components):
        raise ValueError('Component groups must cover every node exactly once')
    if any(key!=node.component_id for key,node in plan.components.items()):
        raise ValueError('Component identity disagrees with plan key')
    groups={group.group_id:group for group in plan.groups}
    if len(groups)!=len(plan.groups): raise ValueError('Component group identities must be distinct')
    owners={member:group.group_id for group in plan.groups for member in group.members}
    for group in plan.groups:
        expected={owners[target] for member in group.members for target in plan.components[member].dependencies if target not in group.members}
        if expected!=set(group.dependencies): raise ValueError('Component group dependencies disagree with source graph')
    from tools.conversion_tools.component_order import order_component_groups
    if plan.groups!=order_component_groups(plan.components):
        raise ValueError('Component groups are not the current deterministic SCC order')
    return plan


def component_target(profile):
    """Persist only policy/platform identities, never API keys or model request contents."""
    return dict(java_version=profile.java_version,java_home=profile.java_home,
                conversion_policy=conversion_policy(profile),component_policy=COMPONENT_POLICY_VERSION)


def input_revision(plan,group,target):
    """Consumer membership is bookkeeping; source, configuration and dependency choices are identity."""
    return digest(dict(target=target,components={member:plan.components[member].model_dump(mode='json',
        exclude={'unit_ids','operations','source_characters'}) for member in sorted(group.members)}))


def component_group(plan,component_id):
    """Locate the indivisible group for a current configured or neutral component."""
    return next((group for group in plan.groups if component_id in group.members),None)


def external_group(plan,group):
    """External policy records have no native component implementation to promote here."""
    return all(plan.components[member].kind in {'external_dependency','operation_contract'} for member in group.members)
