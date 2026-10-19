"""Build a sanitized intake inventory of channel-loaded service and connector definitions."""

from pathlib import Path
from xml.etree import ElementTree
from tools.component_inventory_tools.loaded_service_documents import load_service_documents
from tools.component_inventory_tools.service_definitions import index_service_definitions


def service_inventory(workspace, channels):
    """Record loaded definitions and explicit registry issues without resolving unused services."""
    workspace = Path(workspace).resolve()
    result = {}
    for channel in channels:
        try:
            mappings, documents = load_service_documents(workspace, channel)
            services, connectors = index_service_definitions(workspace, channel, mappings, documents)
            result[channel] = dict(services=services, connectors=connectors, issues=[])
        except (OSError, ValueError, ElementTree.ParseError) as exc:
            result[channel] = dict(services={}, connectors={}, issues=[str(exc)])
    return result
