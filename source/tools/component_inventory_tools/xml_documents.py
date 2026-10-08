"""Read source XML with external declarations prohibited and reproducible node selectors."""

from xml.etree import ElementTree


def read_xml(path):
    """Parse supplied XML bytes, honoring encoding without permitting entity declarations."""
    data = path.read_bytes()
    probe = data.replace(b"\x00", b"").upper()
    if b"<!DOCTYPE" in probe or b"<!ENTITY" in probe:
        raise ValueError("XML declarations containing DTDs/entities are not supported")
    return ElementTree.fromstring(data)


def tag_name(node):
    """Return a namespace-independent XML element name."""
    return node.tag.rsplit("}", 1)[-1]


def walk_nodes(root, prefix=""):
    """Yield nodes with exact occurrence selectors, preserving duplicate definitions."""
    selector = prefix or "/" + tag_name(root) + "[1]"
    yield root, selector
    counts = {}
    for child in root:
        tag = tag_name(child)
        counts[tag] = counts.get(tag, 0) + 1
        yield from walk_nodes(child, selector + "/" + tag + "[" + str(counts[tag]) + "]")

