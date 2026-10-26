"""Apply the confirmed Composer keyed/indexed wrapper policy without merging occurrences."""

INDEXED_WRAPPERS = frozenset((
    'AmtaIColl', 'CCIColl', 'ICollFEditQry', 'ICollFEditQryWEB',
    'IndexedCollectionFormatHolder', 'IndexedCollectionToFormat', 'IndexedCollFormat',
    'IColl', 'ICollSetLength', 'IndexCollectionFormatDLS', 'IndexCollectionFormatDLSWEB',
    'CCIndexedCollectionFormat',
))


def collection_key(element):
    """References declare no key; named children use exact id/dataName/name precedence."""
    if element.tag in ('refFmt', 'refFormat'):
        return None
    return next((element.get(name) for name in ('id', 'dataName', 'name')
                 if element.get(name, '').strip()), None)


def effective_children(wrapper, is_decorator):
    """Keep indexed order or last keyed children and their own following decorators."""
    children = list(wrapper)
    if wrapper.tag in INDEXED_WRAPPERS:
        return children
    latest = {collection_key(child): child for child in children
              if not is_decorator(child) and collection_key(child) is not None}
    selected, keep_decorators = [], True
    for child in children:
        if is_decorator(child):
            if keep_decorators:
                selected.append(child)
        else:
            key = collection_key(child)
            keep_decorators = key is None or latest[key] is child
            if keep_decorators:
                selected.append(child)
    return selected
