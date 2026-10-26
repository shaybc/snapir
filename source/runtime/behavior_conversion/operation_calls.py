"""Bind converted operation invocations to persisted native XML service contracts."""

import json
import re

from tools.state_store_tools.operation_calls import get_contract, set_contract_status
from runtime.java_public_type import _code

INSTRUCTION = '''operation_calls records replace Composer CCComplexOpStep dispatch with real
HTTP clients to the target native operation. Use the saved method, path and application/xml
format contracts. Inject the target base URL using its base_url_property; never hardcode a
host, fall back to Composer, inline the callee implementation or fabricate its response.
In Spring wrappers bind each caller bean's host argument with @Value("${<base_url_property>}")
using the actual saved property name, with no invented host default. Supply it to the client.
Map the calling operation's values to the target request format, and merge the target reply
back into the calling flow as the supplied configuration and source require. Preserve return
codes, error XML, conditional routing and timeout behavior. If mappings or transaction semantics
cannot be established from evidence, report unresolved_questions instead of inventing them.
Provide executable HTTP adapter tests using a local stub server for request path/body, success,
target business errors, transport failures and timeouts. Calling the service is required;
merely storing the operation name or returning a constant is not a replacement.
native_http_contract defines this operation's public endpoint. Expose that exact POST path
with application/xml request/success/error bodies matching the saved Mapper formats.
Endpoint contracts can be planned before implementations are assembled or validated; neither
state proves deployment. Runtime host addresses are deployment configuration.'''


def attach_operation_calls(conn, config, payload, calls=(), operation_key=None):
    """Attach authoritative contracts so generated code and reuse hashes see the same facts."""
    if calls:
        payload['operation_calls'] = list(calls)
    if operation_key:
        payload['native_http_contract'] = get_contract(conn, config.run_id, operation_key)
        payload['native_http_contract'].pop('status', None)
    return payload


def validate_operation_clients(bundle, calls):
    """Reject missing native transport or an unchanged Composer invocation before compilation."""
    if not calls:
        return
    sources = '\n'.join(file.content for file in bundle.files if file.path.startswith('src/main/java/'))
    code = _code(sources)
    if re.search(r'\bCCComplexOpStep\b|\bopExecuteName\b', code):
        raise ValueError('Operation call must use native HTTP transport, not Composer dispatch')
    if not re.search(r'\b(?:HttpClient|RestClient|WebClient|HttpURLConnection)\b', code):
        raise ValueError('Operation client has no native HTTP transport')
    if not re.search(r'\.\s*(?:send|sendAsync|retrieve|exchange|exchangeToMono|getInputStream)\s*\(', code):
        raise ValueError('Operation client must execute its HTTP request')
    for call in calls:
        contract = call['service_contract']
        # A slash-normalizing join may keep the path's leading slash in the join.
        joined_path = (r'\b(?P<base>[\w.]+)\s*\+\s*\(\s*(?P=base)\.endsWith\s*\(\s*"/"\s*\)'
            r'\s*\?\s*""\s*:\s*"/"\s*\)\s*\+\s*' + re.escape(json.dumps(contract['path'].lstrip('/'))))
        if contract['path'] not in sources and not re.search(joined_path, sources):
            raise ValueError('Operation client must use saved target path: ' + contract['path'])
    if bundle.unresolved_questions:
        raise ValueError('Operation call behavior is unresolved: ' + '; '.join(bundle.unresolved_questions))


def order_closures(conn, config, closures):
    """Order native operations by dependencies; preserve the old order for call-free runs."""
    from runtime.intake_plan import has_intake_plan, dependency_plan_context
    if has_intake_plan(conn, config.run_id):
        order = {key: index for index, key in enumerate(dependency_plan_context(conn, config.run_id)['order'])}
        return sorted(closures, key=lambda item: order[item['channel'] + '/' + item['operation_id']])
    from tools.state_store_tools.operation_calls import load_graph
    from tools.operation_call_tools.ordering import ordered_operations
    graph = load_graph(conn, config.run_id)
    if not graph or not graph['calls']:
        return closures
    by_key = {item['channel'] + '/' + item['operation_id']: item for item in closures}
    available = {row[0] for row in conn.execute("SELECT operation_key FROM operation_service_contracts WHERE run_id=? AND status='validated'", (config.run_id,))}
    return [by_key[key] for key in ordered_operations(graph, by_key, available)]


def validate_endpoint(files, contract):
    """Require the generated controller to expose the saved POST route, including split mappings."""
    if not contract:
        return
    from tools.validation_tools.java_comments import mask_java_comments
    for path, source in files.items():
        if not path.endswith('.java'):
            continue
        source = mask_java_comments(source)
        if not re.search(r'@(?:[\w.]*\.)?RestController\b', source):
            continue
        prefix = re.search(r'@RequestMapping\s*\([^)]*?"([^"]+)"[^)]*\)\s*(?:public\s+)?class', source, re.S)
        for match in re.finditer(r'@PostMapping\s*\(([^)]*)\)', source, re.S):
            value = re.search(r'"([^"]*)"', match[1])
            route = (prefix[1] if prefix else '') + (value[1] if value else '')
            if route == contract['path']:
                return
    raise ValueError('Generated controller must expose POST ' + contract['path'])


def mark_assembled(conn, run_id, key):
    """Advance contract readiness only after accepted operation assembly."""
    set_contract_status(conn, run_id, key, 'assembled')


def verify_operation_contracts(conn, config, calls, profile=None):
    """Reject client reuse when the target contract or its source configuration changed."""
    for call in calls:
        if call['service_contract'].get('published_api'):
            from tools.operation_call_tools.published_calls import verify_pinned_call
            verify_pinned_call(conn, config.run_id, call)
            continue
        current = get_contract(conn, config.run_id, call['callee'])
        if current['fingerprint'] != call['service_contract']['fingerprint']:
            raise ValueError('Target operation contract changed; reconvert caller: ' + call['callee'])
        channel, operation = call['callee'].split('/', 1)
        from tools.conversion_tools.scoped_workflow.preparation import is_scoped_run
        if is_scoped_run(conn, config.run_id):
            if profile is None:
                raise ValueError('Scoped target verification requires its conversion profile')
            from runtime.scoped_native.scope import verify_context
            verify_context(conn, config, profile, call['callee'])
            continue
        from tools.conversion_tools.behavior_evidence_freshness import verify_configuration_sources
        verify_configuration_sources(conn, config, operation, channel)


def validate_client_configuration(files, calls):
    """Require caller wrappers to bind every target host from deployment configuration."""
    if not calls:
        return
    source = '\n'.join(files.values())
    for call in calls:
        property_name = call['service_contract']['base_url_property']
        if '${' + property_name + '}' not in source:
            raise ValueError('Configure target base URL through ${' + property_name + '}')
