"""Recognize opaque framework composition without manufacturing source-derived hook sequences."""
def composition_boundaries(configured, boundaries):
    """Select proven basic boundary results belonging to this configured unit only."""
    if not boundaries: return []
    from tools.behavior_verification.format_lifecycle import basic_identity
    result = []
    def visit(node):
        name = node.get('java_class')
        boundary = boundaries.get('basic_boundaries', {}).get(basic_identity(configured['unit_id'], name)) if name else None
        if boundary: result.extend(boundary.get('framework_boundaries', []))
        for child in node.get('children', []): visit(child)
    visit(configured['effective_configuration'])
    for node in configured.get('referenced_definitions', []): visit(node)
    return result


def framework_occurrence(configured, node, boundaries):
    """Relax source-derived chain proof for this binary-owned occurrence, not unrelated siblings."""
    if not boundaries: return False
    from tools.behavior_verification.format_lifecycle import basic_identity
    name = node.get('java_class')
    boundary = boundaries.get('basic_boundaries', {}).get(basic_identity(configured['unit_id'], name)) if name else None
    return bool(boundary and boundary.get('framework_boundaries'))
