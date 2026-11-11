"""Attach compact binary-boundary ownership and existing manual guidance to generation."""
from tools.conversion_tools.scoped_reuse.fingerprints import digest

INSTRUCTION = """
framework_boundaries identify original runtime code supplied only by configured framework JARs.
Missing framework source is expected, not a request to recreate it or a conversion blocker.
Convert the supplied application business behavior using the existing Composer explanations.
Do not generate framework classes, Composer inheritance, a Context clone, or a generic tag runtime.
Do not add original Composer JARs to native production dependencies. The original side of comparisons
runs with those binaries; native code implements business results with native Java APIs and libraries.
Application source and its parser obligations remain authoritative for application-specific behavior.
Do not invent proprietary source/checklist evidence or claim equivalence from compilation alone.
"""


def attach_framework_context(request, boundaries):
    """Deduplicate relevant boundary metadata; never include a whole archive inventory."""
    declared = {item['declaring_class'] for item in boundaries if item.get('declaring_class')}
    records = {digest(item): item for item in boundaries if item.get('class_name') not in declared}
    request['framework_boundaries'] = [records[key] for key in sorted(records)]
    request['framework_boundary_policy'] = 'framework-binary-v1'
    request['framework_boundary_instruction'] = INSTRUCTION


def dependency_boundaries(plan, group):
    """Include relevant binary dependencies even when the application entry itself has source."""
    from tools.framework_boundaries.inventory import owner, current
    if not current(): return []
    pending, seen, result = list(group.members), set(), []
    while pending:
        key = pending.pop()
        if key in seen: continue
        seen.add(key)
        node = plan.components[key]
        if node.kind != 'java_implementation':
            library = owner(node.label)
            if library: result.append(dict(class_name=node.label, **library))
        pending.extend(node.dependencies)
    return result
