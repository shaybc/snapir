"""Explicit foundation ownership and source-backed proposals, without converting entire archives."""
from copy import deepcopy

POLICY = 'approved-foundations-v2'


def foundation_selection(discovery):
    """Return copied class evidence, explicit ownership, and reviewable shared-base proposals."""
    classes = deepcopy(discovery['classes'])
    owners = {}
    groups = discovery.get('foundation_groups', {})
    if not isinstance(groups, dict):
        raise ValueError('foundation_groups must be an object')
    for label, members in groups.items():
        if not isinstance(members, list) or not members or len(set(members)) != len(members):
            raise ValueError('Foundation groups require distinct exact class names')
        for name in members:
            if name.startswith(('java.', 'javax.', 'jdk.')):
                raise ValueError('JDK classes are not foundation conversion targets: ' + name)
            if name in owners:
                raise ValueError('Original class belongs to multiple foundation groups: ' + name)
            owners[name] = label
            classes.setdefault(name, dict(name=name, file=None, project=None, abstract=True,
                framework=True, kind='support', dependencies=[], ancestors=[], issues=[
                    'Foundation behavior requires source: ' + name + '; add foundation_source_roots']))
    concrete = {name for name, item in classes.items() if item['kind'] in {'format', 'decorator'}
                and not item['abstract'] and not item['framework'] and name not in owners}
    usage = {}
    for name in sorted(concrete):
        item = classes[name]
        for ancestor in item.get('ancestors', []):
            if ancestor.startswith(('java.', 'javax.', 'jdk.')):
                continue
            usage.setdefault(ancestor, []).append(name)
    proposals = []
    for name, consumers in sorted(usage.items()):
        source = classes.get(name, {})
        # Hierarchy ancestors are proposals only; explicit configuration decides ownership.
        if len(consumers) > 1 or source.get('abstract') or name.endswith('.FormatElement'):
            proposals.append(dict(original_class=name, consumers=consumers, source_available=bool(source.get('file')),
                                  selected_group=owners.get(name)))
    return classes, owners, concrete, proposals


def unowned_bases(members, classes, proposals, owners):
    """List shared ancestor behavior still requiring an explicit foundation selection."""
    candidates = {item['original_class'] for item in proposals} - set(owners)
    return sorted({ancestor for name in members for ancestor in classes[name].get('ancestors', [])
                   if ancestor in candidates})


def verify_selection(config, manifest):
    """Do not continue an old preparation after changing foundation ownership/source locations."""
    if manifest.get('foundation_settings') != dict(groups=config.get('foundation_groups', {}),
                                                   source_roots=config.get('foundation_source_roots', [])):
        raise ValueError('Foundation configuration differs from this preparation; rediscover and prepare again')
