"""Select exact ordered child subtrees without splitting source text or losing configuration."""
from copy import deepcopy
from tools.conversion_tools.scoped_reuse.fingerprints import digest


def subtree_at(tree, selector):
    """Resolve an occurrence path; references remain atomic within their owning subtree."""
    node = tree
    for index in selector:
        node = node['children'][index]
    return node


def partition_tree(tree, selector, children):
    """Replace only previously converted direct children with their exact contract references."""
    node = deepcopy(subtree_at(tree, selector))
    for index, child in enumerate(node.get('children', [])):
        path = tuple(selector) + (index,)
        if path in children:
            reference = {key:value for key,value in children[path].items()
                if key in {'group_id','contract_revision','result_revision'}}
            node['children'][index] = dict(native_subtree=reference,
                original_selector=list(path), configuration_hash=digest(child))
    return node


def parent_configuration(tree, selector):
    """Keep inherited attributes/decorators and occurrence positions, without sibling bodies."""
    return [dict(selector=list(selector[:depth]), configuration={key: deepcopy(value)
        for key, value in subtree_at(tree, selector[:depth]).items() if key != 'children'})
        for depth in range(len(selector))]


def splittable_children(tree, selector):
    """Return ordered structural cuts; leaf text, references and cyclic graphs are indivisible."""
    node = subtree_at(tree, selector)
    if node.get('reference_definition_id'):
        return []
    return [tuple(selector) + (index,) for index, child in enumerate(node.get('children', []))
            if isinstance(child, dict)]


def partition_identity(group_id, tree, selector):
    """Bind part identity to its original parent occurrence and complete configuration bytes."""
    return group_id + '-subtree-' + digest(dict(selector=list(selector), tree=tree))[:24]
