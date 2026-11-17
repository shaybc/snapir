"""Validate foundation export ownership without compiling or executing generated Java."""
import re


def exports(manifest, components):
    """Accept many-to-one or split native exports, with explicit original-class coverage."""
    if not isinstance(components, list) or not components:
        raise ValueError('Foundation response requires native exports')
    covered, native_names = set(), set()
    for item in components:
        if not isinstance(item, dict):
            raise ValueError('Foundation exports must be objects')
        originals = item.get('covered_original_classes')
        if not isinstance(originals, list) or not originals or not all(isinstance(name, str) for name in originals):
            raise ValueError('Each foundation export must identify covered_original_classes')
        if set(originals) - set(manifest['members']):
            raise ValueError('Foundation export claims an original class outside its selected group')
        native = item.get('native_class')
        if not isinstance(native, str) or not native.startswith(manifest['native_package'] + '.') or not re.fullmatch(r'[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)+', native, re.ASCII):
            raise ValueError('Foundation export requires a native class in the assigned package')
        if native in native_names:
            raise ValueError('Duplicate foundation native export')
        if item.get('kind') not in {'class', 'abstract_class', 'interface'}:
            raise ValueError('Foundation export kind must be class, abstract_class or interface')
        for field in ('constructors', 'methods', 'hooks'):
            if not isinstance(item.get(field), list) or not all(isinstance(value, str) and value.strip() for value in item[field]):
                raise ValueError('Foundation export must declare its actual ' + field)
        if not isinstance(item.get('integration_notes'), str) or not item['integration_notes'].strip():
            raise ValueError('Foundation export must explain how subclasses/delegates use it')
        covered.update(originals); native_names.add(native)
    if covered != set(manifest['members']):
        raise ValueError('Foundation exports do not cover every selected original class')
    return native_names
