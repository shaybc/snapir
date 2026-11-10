"""Describe external connection inputs without opening deployment connector files."""

import re

from tools.validation_tools.java_comments import mask_java_comments


def is_deployment_connector(path):
    """Recognize the Composer connector template and deployed XML by file name."""
    return str(path).replace('\\', '/').rsplit('/', 1)[-1].lower() in {'dseconnector.tmp', 'dseconnector.xml'}


def configuration_contract(sources):
    """Collect literal configuration keys from code without collecting their values.

    Types remain unknown for generic lookups. Dynamic keys remain deployment
    requirements; this bounded inspection does not claim a complete schema.
    """
    parameters = {}
    types = {'getProperty': 'String', 'getString': 'String', 'getInt': 'int',
             'getLong': 'long', 'getBoolean': 'boolean'}
    for identity, content in sources.items():
        code = mask_java_comments(content)
        for match in re.finditer(r'\b(getProperty|getString|getInt|getLong|getBoolean|tryGetValueAt|getValueAt)\s*\(\s*"([^"\\]+)"', code):
            key = match[2]
            item = parameters.setdefault(key, dict(name=key, type=None, required=None, evidence=[]))
            kind = types.get(match[1])
            if kind and item['type'] in (None, kind):
                item['type'] = kind
            elif kind:
                item['type'] = 'unknown'
            item['evidence'].append(dict(source=identity, accessor=match[1]))
    return dict(version=1, origin='source_accessors',
                parameters=[parameters[key] for key in sorted(parameters)],
                completeness='bounded_source_keys; dynamic and documented inputs require review',
                values='external_deployment_only')
