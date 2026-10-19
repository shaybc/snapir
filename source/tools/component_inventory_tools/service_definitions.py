"""Index loaded services/connectors without exposing connection secrets."""

import re
from xml.etree import ElementTree
from tools.component_inventory_tools.xml_documents import tag_name, walk_nodes


def sanitized_attributes(attributes):
    """Keep configuration keys and non-secret identity; remove credential values."""
    result = {}
    for key, value in attributes.items():
        if re.search(r'password|passwd|secret|token|credential|^user(name)?$', key, re.I):
            result[key] = {'deployment_setting': key}
        elif re.search(r'url|endpoint', key, re.I):
            result[key] = {'deployment_setting': key, 'scheme': value.split(':', 2)[:2] if value.startswith('jdbc:') else value.partition(':')[0]}
        else:
            result[key] = value
    return result


def index_service_definitions(workspace, channel, mappings, documents):
    """Retain distinct instances and their configured pool references by channel."""
    services, connectors = {}, {}
    for document in documents.values():
        parents = {id(child): parent for parent in document['root'].iter() for child in parent}
        for node, selector in walk_nodes(document['root']):
            identity = node.get('id')
            if not identity:
                continue
            tag = tag_name(node)
            mapping = mappings.get(('services', tag))
            is_connector = node.get('JDBCDriver') is not None or node.get('dbType') is not None
            if not mapping and not is_connector:
                continue
            # Never forward raw XML attributes containing credentials to the model.
            attrs = sanitized_attributes(node.attrib)
            public = ElementTree.Element(tag)
            for key, value in attrs.items():
                public.set(key, value if isinstance(value, str) else '<deployment-setting>')
            item = dict(id=identity, tag=tag, attributes=attrs, implementation=mapping['implementation'] if mapping else '',
                        path=document['path'].relative_to(workspace).as_posix(), selector=selector,
                        origin_channel=document['channel'], registry=mapping['registry'] if mapping else '',
                        configuration_xml=ElementTree.tostring(public, encoding='unicode'))
            if is_connector:
                parent = parents.get(id(node))
                if parent is not None and parent.get('id'):
                    parent_tag = tag_name(parent)
                    parent_mapping = mappings.get(('services', parent_tag)) or mappings.get(('types', parent_tag))
                    item['manager'] = dict(tag=parent_tag, attributes=sanitized_attributes(parent.attrib),
                        implementation=parent_mapping['implementation'] if parent_mapping else '')
            target = connectors if is_connector else services
            target.setdefault(identity, []).append(item)
    for target in (services, connectors):
        for identity, items in target.items():
            local = [item for item in items if item['origin_channel'] == channel]
            if local:
                target[identity] = local
    return services, connectors
