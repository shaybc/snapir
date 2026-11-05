"""External wrapper requirements; native internal call flow remains operation-owned."""
from runtime.service_generation.shared_runtime import runtime_sources

VERSION = 'named-database-request-isolation-v1'
INSTRUCTION = '''
Use the supplied maintained integration library; do not recreate its implementation in wrapper files.
Import NativeRuntimeConfiguration on the Spring application, exclude DataSourceAutoConfiguration
because named pools are owned by the shared registry. Include actuator and Spring MVC/JDBC dependencies.
Keep every accepted operation, formatter and configured-step Java file byte-for-byte unchanged.
For an XML String operation API, call that API directly: do not parse/map XML a second time.
Use NativeRuntimeProperties.operation.database to select the named database; never a request-supplied name.
For a Connection argument use DatabaseExecution.execute(name, connection -> actualOperation.execute(...)).
For a DataSource constructor use DatabaseRegistry.resolve(name); do not borrow an extra connection.
Retain existing source transaction semantics. Do not introduce retries, commits or new @Transactional behavior.
The controller is stateless. EVERY mutable step and operation bean must have @Scope("prototype").
Use an ObjectProvider to obtain the operation per invocation; do not inject a prototype once into a singleton.
Preserve exact named @Bean binding_id roles and their matching @Qualifier values from the accepted contract.
Read OperationContextFactory.create() per request and pass its exact-case initialization values through
the accepted parameter/constructor/setter APIs. Do not lowercase or approximately match context names.
Identify consumed initialization keys in a wrapper-owned resource initialization-bindings.json, containing
{"consumed_keys":[...]} only. Fail startup for configured unsupported keys; do not silently ignore them.
Use actual external inputs, not synthetic production replies or test drivers in src/main.
Return raw XML using the configured http.path property and application/xml, not a JSON-quoted String.
Configuration properties, named pools, initialization and probes are converter-owned resources; preserve them.
Generate executable tests that start real Spring configuration with a substitute DatabaseRegistry before refresh,
retrieve real named steps and two distinct operation graphs, then exercise real HTTP request/response handling.
Use Spring Boot RANDOM_PORT/TestRestTemplate. When JDBC is required, supply a test JDBC Driver or Mockito
JDBC objects via the substituted registry. Do not mock the operation or configured steps. Test the actual
success/error branches from the supplied contract, initialization and concurrent requests. Where JDBC is
required, also test configured database selection and connection closure. Use independent external resources
for concurrent invocations and assert the expected response for each request; never share one stateful cursor.
Put all external substitute beans under the actual names before refresh. @MockitoBean DatabaseRegistry is
also supported. Never require real credentials, database/API servers, production resource factories or network calls.
Test that different requests have distinct step state while they share the same DatabaseRegistry.
Use only the actual accepted overloads supplied in operation.contract.service_api and approved_sources.
Do not use hardcoded vendor credentials or change dependency versions supplied by the converter.
'''


def attach_wrapper_contract(payload, spec):
    payload['microservice_deployment'] = spec.model_dump(mode='json')
    payload['shared_runtime_api'] = {str(p.relative_to(runtime_sources())):p.read_text(encoding='utf-8')
        for p in runtime_sources().joinpath('src/main/java').rglob('*.java')}
    payload['wrapper_requirement'] = dict(version=VERSION, description=INSTRUCTION)
