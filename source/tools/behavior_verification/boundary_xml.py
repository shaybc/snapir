"""XML comparison that preserves prefixes, significant whitespace and empty/nil distinctions."""
from xml.dom import minidom, Node
from xml.parsers.expat import ExpatError


def xml_structure(text, insignificant_whitespace_paths=()):
    """Normalize attribute order only, plus whitespace at explicitly approved element paths."""
    if '<!DOCTYPE' in text.upper() or '<!ENTITY' in text.upper():
        raise ValueError('DTD/entity-bearing XML is not supported by the boundary comparator')
    fragment = False
    try:
        document = minidom.parseString(text)
    except ExpatError:
        document = minidom.parseString('<boundary-fragment>' + text + '</boundary-fragment>')
        fragment = True

    def node_value(node, path):
        if node.nodeType == Node.ELEMENT_NODE:
            path = path + '/' + node.tagName
            attributes = tuple(sorted((item.name, item.namespaceURI, item.value)
                                      for item in node.attributes.values()))
            children = []
            for child in node.childNodes:
                value = node_value(child, path)
                if value is None:
                    continue
                if value[0] == 'text' and children and children[-1][0] == 'text':
                    children[-1] = ('text', children[-1][1] + value[1])
                else:
                    children.append(value)
            return ('element', node.tagName, node.namespaceURI, attributes, tuple(children))
        if node.nodeType in (Node.TEXT_NODE, Node.CDATA_SECTION_NODE):
            if path in insignificant_whitespace_paths and not node.data.strip():
                return None
            return ('text', node.data)
        if node.nodeType == Node.COMMENT_NODE:
            return ('comment', node.data)
        if node.nodeType == Node.PROCESSING_INSTRUCTION_NODE:
            return ('instruction', node.target, node.data)
        raise ValueError('Unsupported XML node type: ' + str(node.nodeType))

    return tuple(node_value(node, '') for node in (document.documentElement.childNodes if fragment else document.childNodes))

