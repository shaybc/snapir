"""Read optional analyzer structure without turning diagnostic metadata into an acceptance gate."""


def read_class_structure(entry, sources, paths):
    """Bind source metadata to the same supplied revisions; binary bodies are never requested."""
    structure = entry.find('class-structure')
    if structure is None:
        return dict(classes=[], issues=['Class structure was not recorded'])
    result = dict(classes=[], issues=[item.get('message') for item in structure.findall('issue')])
    result['issue_records'] = [dict(item.attrib) for item in structure.findall('issue')]
    for item in structure.findall('class'):
        value = dict(item.attrib)
        if item.get('source_identity'):
            source = sources.get(item.get('source_identity'))
            if source is None or source['content_hash'] != item.get('source_hash'):
                result['issues'].append('Diagnostic structure has no matching source revision: ' + item.get('name', '?'))
                continue
            value['source_file'] = paths.get(item.get('source_identity'))
        value['parents'] = [dict(parent.attrib) for parent in item.findall('parent')]
        value['fields'] = [dict(field.attrib) for field in item.findall('field')]
        result['classes'].append(value)
    return result
