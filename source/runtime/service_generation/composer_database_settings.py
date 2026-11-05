"""Read non-secret JDBC settings from an operation's effective Composer pool binding."""
import re
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree

from tools.component_inventory_tools.loaded_service_documents import load_service_documents
from tools.component_inventory_tools.service_definitions import index_service_definitions
from tools.component_inventory_tools.xml_documents import walk_nodes


def credential_free_url(value):
    """Reject embedded credentials and unresolved substitutions; never return credential values."""
    if not isinstance(value,str) or not value.startswith('jdbc:'):return False
    decoded=unquote(unquote(value))
    if re.search(r'\$\{|#\{|%\w+%|[\r\n]',decoded):return False
    if re.search(r'//[^/?#]*@',decoded):return False
    if re.search(r'^jdbc:oracle:[^:]+:(?!@)[^@]+@',decoded,re.I):return False
    return not re.search(r'(?:^|[?;&:(,\s])(?:user(?:name|\s*id)?|uid|pass|[\w.-]*(?:password|passwd|pwd|secret|token|credential)[\w.-]*)\s*=',decoded,re.I)


def discover_database_settings(workspace, channel, records):
    """Resolve one operation-linked JDBC pool; ambiguity remains an explicit unresolved input."""
    result=dict(jdbcUrl='',driverClass='',issues=[],sources=[])
    jdbc=[r for r in records if r.get('resource_kind')=='jdbc' and r.get('channel')==channel]
    if not jdbc:
        result['issues'].append('No operation-linked Composer JDBC pool binding is available; the connection may be caller-supplied.')
        return result
    pools={r.get('connector_id') for r in jdbc}
    if len(pools)!=1 or not next(iter(pools)):
        result['issues'].append('Multiple or unresolved Composer JDBC pool bindings; no default pool was guessed.')
        return result
    pool=next(iter(pools));workspace=Path(workspace).resolve()
    try:
        mappings,documents=load_service_documents(workspace,channel)
        services,connectors=index_service_definitions(workspace,channel,mappings,documents)
    except (ValueError,OSError,ElementTree.ParseError):
        result['issues'].append('Loaded Composer service configuration could not be resolved.')
        return result
    candidates=connectors.get(pool,[])
    if len(candidates)!=1:
        result['issues'].append('The bound Composer pool is missing or ambiguous in the loaded channel configuration.')
        return result
    for record in jdbc:
        service=services.get(record.get('service_id'),[])
        if len(service)!=1 or service[0]['attributes'].get('poolName')!=pool:
            result['issues'].append('The operation service-to-pool binding changed; refresh its source evidence.')
            return result
    connector=candidates[0]
    document=documents.get(str((workspace/connector['path']).resolve()))
    nodes=[node for node,selector in walk_nodes(document['root']) if selector==connector['selector']] if document else []
    if len(nodes)!=1 or nodes[0].get('id')!=pool:
        result['issues'].append('The configured pool source could not be located exactly.')
        return result
    node=nodes[0];driver=node.get('JDBCDriver','')
    if any(r.get('driver_class') and r['driver_class']!=driver for r in jdbc):
        result['issues'].append('The Composer driver changed; refresh its source evidence.')
        return result
    if driver and not re.search(r'\$\{|#\{|%\w+%',driver):result['driverClass']=driver
    else:result['issues'].append('The bound Composer pool has no resolved JDBC driver class.')
    urls={value for key,value in node.attrib.items() if 'url' in key.lower() and value.startswith('jdbc:')}
    if len(urls)!=1:
        result['issues'].append('The bound Composer pool has no unique configured JDBC URL.')
    elif not credential_free_url(next(iter(urls))):
        result['issues'].append('The JDBC URL contains credentials or unresolved substitutions; supply a credential-free URL. No URL was exported.')
    else:result['jdbcUrl']=next(iter(urls))
    result['sources']=[dict(path=connector['path'],selector=connector['selector'],connector_id=pool)]
    return result
