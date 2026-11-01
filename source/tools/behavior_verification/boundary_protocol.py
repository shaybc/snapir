"""Typed XML transport between Python and isolated JVM boundary executions."""
import base64
from xml.etree import ElementTree as ET


def value_element(value, name='value'):
    node = ET.Element(name)
    if value is None:
        node.set('type', 'null')
    elif isinstance(value, bool):
        node.set('type', 'boolean'); node.text = str(value).lower()
    elif isinstance(value, (int, float)):
        node.set('type', 'number'); node.text = str(value)
    elif isinstance(value, str):
        node.set('type', 'string')
        node.text = base64.b64encode(value.encode('utf-16-be', errors='surrogatepass')).decode('ascii')
    elif isinstance(value, dict) and set(value) == {'$date_millis'}:
        node.set('type', 'date'); node.text = str(int(value['$date_millis']))
    elif isinstance(value, dict) and set(value) == {'$decimal'}:
        from decimal import Decimal
        node.set('type', 'number'); node.text = str(Decimal(value['$decimal']))
    elif isinstance(value, dict):
        node.set('type', 'map')
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError('Boundary map keys must be strings')
            entry = ET.SubElement(node, 'entry', key=key); entry.append(value_element(item))
    elif isinstance(value, (list, tuple)):
        node.set('type', 'list')
        for item in value:
            node.append(value_element(item))
    else:
        raise ValueError('Unsupported boundary value: ' + type(value).__name__)
    return node


def read_value(node):
    kind = node.get('type')
    if kind == 'null': return None
    if kind == 'string': return base64.b64decode(node.text or '', validate=True).decode('utf-16-be', errors='surrogatepass')
    if kind == 'boolean': return node.text == 'true'
    if kind == 'number':
        text = node.text or ''
        return int(text) if all(char not in text.lower() for char in '.e') else {'$decimal': text}
    if kind == 'date': return {'$date_millis': int(node.text)}
    if kind == 'list': return [read_value(child) for child in node]
    if kind == 'map':
        result = {}
        for child in node:
            if child.get('key') in result: raise ValueError('Duplicate boundary map key')
            result[child.get('key')] = read_value(child.find('value'))
        return result
    raise ValueError('Unsupported boundary protocol type: ' + str(kind))


def configuration_element(node, definitions, visited=()):
    """Expand only evidenced format references; cycles remain explicit unsupported bindings."""
    reference = node.get('reference_definition_id')
    if reference:
        if reference in visited or reference not in definitions:
            raise ValueError('Unavailable/cyclic boundary format reference: ' + reference)
        return configuration_element(definitions[reference], definitions, (*visited, reference))
    if not node.get('java_class'):
        children = node.get('children', [])
        if node.get('tag') != 'fmtDef' or len(children) != 1:
            raise ValueError('Boundary format requires one implementing root')
        return configuration_element(children[0], definitions, visited)
    result = ET.Element('component', implementation=node['java_class'])
    result.append(value_element(node.get('attributes', {}), 'attributes'))
    for child in node.get('children', []):
        result.append(configuration_element(child, definitions, visited))
    for decorator in node.get('decorators', []):
        configured = configuration_element(decorator, definitions, visited)
        configured.tag = 'decorator'; result.append(configured)
    return result

