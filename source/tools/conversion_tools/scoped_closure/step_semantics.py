"""Classify implementation-free routing nodes without using business step labels."""

def step_implementation(element, mappings):
    """Honor explicit implementations, then named registry bindings, then the default step class."""
    return element.get('implClass') or mappings.get(element.get('id')) or mappings.get('opStep')


def routing_only(element, mappings):
    """Recognize pure fallback routing; parameters and unevidenced conditional execution stay blocked."""
    if step_implementation(element, mappings):
        return False
    if len(element) or (element.text and element.text.strip()):
        return False
    attributes = element.attrib
    if not (attributes.get('onOtherDo') or attributes.get('onOtherDoDefault')):
        return False
    return all(name in {'id', 'onlyFor', 'onOtherDo', 'onOtherDoDefault'} for name in attributes)
