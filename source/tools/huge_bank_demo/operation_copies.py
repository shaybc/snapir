"""Copy complete XML operation families, preserving calls, control flow and business data."""

from copy import deepcopy
from xml.etree import ElementTree


def operation_documents(source):
    """Load operation documents with comments, leaving shared contexts and formats in place."""
    documents = []
    for path in sorted((source / 'composer/Workspace').rglob('*.xml')):
        root = ElementTree.parse(path, parser=ElementTree.XMLParser(target=ElementTree.TreeBuilder(insert_comments=True))).getroot()
        if any(node.tag == 'CCDSEServerOperation' for node in root.iter()):
            documents.append((path.relative_to(source), root))
    return documents


def copy_operations(documents, steps, suffix, replica):
    """Yield a closed operation family with private formats and mixed shared/copied Java steps.

    Context field names, service identifiers, SQL and request/reply business payload names
    are intentionally unchanged. Only definition identities and their references change.
    """
    identities = {node.get('id'): node.get('id') + suffix for _, root in documents for node in root.iter()
                  if node.tag in ('CCDSEServerOperation', 'fmtDef') and node.get('id')}
    classes = {name: name + suffix for _, name, _ in steps}
    for relative, original in documents:
        root = deepcopy(original)
        for node in root.iter():
            if node.tag in ('CCDSEServerOperation', 'fmtDef') and node.get('id'):
                node.set('id', identities[node.get('id')])
            for attribute in ('refid', 'opExecuteName'):
                if node.get(attribute) in identities:
                    node.set(attribute, identities[node.get(attribute)])
            if (node.get('id') or node.get('name')) == 'opExecuteName':
                if node.get('value') in identities:
                    node.set('value', identities[node.get('value')])
                if node.text in identities:
                    node.text = identities[node.text]
            for attribute, value in list(node.attrib.items()):
                if attribute.startswith('on') and attribute.endswith('Return') and value in identities:
                    node.set(attribute, identities[value])
        for operation in root.iter('CCDSEServerOperation'):
            step_names = {node.get('id'): node.get('id') + suffix for node in operation.iter('opStep') if node.get('id')}
            for occurrence, node in enumerate(operation.iter('opStep')):
                if node.get('id'):
                    node.set('id', step_names[node.get('id')])
                # Alternate per occurrence/family so the fixture exercises both shared and private code.
                if (occurrence + replica) % 2 == 0 and node.get('implClass') in classes:
                    node.set('implClass', classes[node.get('implClass')])
                for attribute, value in list(node.attrib.items()):
                    if attribute.startswith('on') and attribute.endswith('Do') and value in step_names:
                        node.set(attribute, step_names[value])
        yield relative.with_name(relative.stem + suffix + '.xml'), ElementTree.tostring(root, encoding='utf-8', xml_declaration=True)
