"""Narrow instructions for independent implementation, mapping and test requests."""

from runtime.behavior_conversion.native_reflection_policy import INSTRUCTION as NO_REFLECTION

IMPLEMENTATION_CONTRACT = '''MANDATORY IMPLEMENTATION CONTRACT — initial response and every correction:
1. No IBM package imports/references and no recreated Composer runtime or reflection.
2. Use specific scalar/native DTO boundary types; no Object/Object[], maps, JSON nodes or raw/Object collections.
3. Reuse supplied accepted native APIs unchanged and preserve source-defined behavior and settings.
4. Return one valid JSON object matching NativeImplementation, with correctly escaped Java strings.
For corrections, repair only the reported defects using implementation_repair when supplied; preserve
unaffected code and previously satisfied rules. Return complete corrected files, not patches.
'''

IMPLEMENTATION = IMPLEMENTATION_CONTRACT + NO_REFLECTION + '''Generate only production native Java files for the selected configured unit.
Original XML, implementing sources and Composer documentation are behavior evidence, not target APIs.
Convert all required supporting behavior; do not import/reference IBM packages or keep IBM runtime
dependencies. Use typed inputs/results, ordinary Java transformations and reusable accepted native
APIs. Preserve runtime settings, defaults, missing/null/empty distinctions, outputs and side effects.
Public boundary parameters/results must use specific scalar or native DTO types: rejected examples
include Object, Object[], Map, HashMap, LinkedHashMap, Hashtable, JsonNode, ObjectNode, raw List/Set/
Collection/Iterable and collections of Object; typed collections such as List<ClientLink> are not
rejected by this typing rule, and internal maps remain allowed.
Expose DTO values through public getters and public constructors/setters. New conditionally written
outputs need observable written flags; null alone cannot distinguish absent from written-null.
Specialize initialization from this unit's XML; do not require the harness to supply sample constants.
Return only NativeImplementation: files under src/main/java/ and unresolved_questions if necessary.
Do not return tests, coverage, API metadata, dependency coordinates, evidence tables or harness bindings.
Imports determine which libraries the application resolves separately. Use the supplied known libraries
where suitable. Do not invent external business behavior. One public top-level type per file, with the
native package matching its path. The application will parse APIs, compile and verify behavior.
'''

TESTS = '''Generate executable JUnit tests only for the frozen native implementation.
Use original XML/implementing sources to determine expected behavior, not the generated implementation
as its own oracle. Use the supplied parsed native APIs and testing platform. Do not modify production
code or invent APIs. The selected_boundary is the required test scope: exercise its selected method,
required DTO accessors and runtime controls. Call the native class/method targets in
selected_boundary.settings_bindings for settings setup. Keep settings isolated between cases;
For conversion-checklist scopes, entries lists allowed native entry calls and native_settings_apis
lists the actual settings methods to exercise; no comparison binding is required.
never import the original framework settings class. Do not add reverse-direction or round-trip tests just
because an unused formatter method exists. Do not weaken assertions to hide a failure; report an
unresolved production defect if the frozen implementation contradicts the original evidence.
Test runtime branches and input/output behavior evidenced by the original sources.
Return only NativeTestBundle: files under src/test/java/, coverage links using exact supplied requirement
IDs, and unresolved_questions. No production files, API contracts, dependency coordinates or bindings.
No IBM references, runtime replicas or handwritten external-interface substitutes. Use supplied mocks
for external services. Metadata/coverage links alone do not establish correctness; tests will run.
'''

MAPPING = '''Resolve only the listed ambiguous mappings between original XML/context and parsed native APIs.
Return NativeMappingSelection with a declarative binding. Choose methods/types from parsed_apis only.
No Java code, tests, expected results, constant sample substitutions or behavior summaries.
Use source=context with an exact original key for scalar values. Use source=object for native DTO
construction and real constructor arguments/public setters. Never combine source=context with properties.
Object properties keys are actual parsed setter method names, such as setValue, not field names.
settings_bindings maps each supplied original runtime-control key to exactly {"class":"native.Type",
"method":"actualPublicStaticMethod"}. Do not use target, owner_type, method_name or a dotted string there.
Use getter names without parentheses. Preserve runtime inputs rather than freezing sample values.
'''

DEPENDENCIES = '''Propose dependency coordinates only for unresolved_imports, using pinned versions.
Reuse existing known_dependencies exactly; do not change versions/scopes. Return NativeDependencyProposal
with only needed dependencies and required_classes corresponding to unresolved imports. No source code,
tests or behavioral claims. Artifact/class availability will be independently verified before acceptance.
Never propose IBM runtime artifacts. Do not guess a dependency when evidence is insufficient.
'''
