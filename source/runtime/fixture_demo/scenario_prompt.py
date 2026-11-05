"""Business-level whole-operation scenario preparation; no implementation generation."""

SCENARIO_PROMPT='''Prepare coherent WHOLE-operation XML/JDBC test scenarios using the supplied original
operation configuration, original component code, frozen native code, and saved shared fixture banks.
Return only JSON matching schema. Do not return Java, edit implementation/metadata or call any endpoint.
This is preparation for the standard standalone entry: public String execute/process(String,
Connection), then (String, DataSource), then (String), in that priority. Its recursive constructors
receive the same JDBC resource. Use the actual entry's configured defaults for other runtime inputs.
If a needed input cannot reach that API, report it unresolved; never assume an uncalled overload.

Select a primary successful scenario that exercises the complete normal path, including the real
configured steps and response formatter's resource lookups. Do not choose an empty/invalid request
or an early error to avoid resources. Preserve case-sensitive consuming field and column names.
Follow actual request unformatting (padding removal, defaults, etc.) when preparing procedure inputs.
Use the returned rows as inputs to ALL later queries, child formats and decorators. Every SQL string,
parameter order, output index/type and status constant must follow supplied source, not a guess.
Respect defaults, branch conditions, XML tag/attribute structure, escaping and null/empty behavior.
Do not require Composer mechanisms (context or tags) to appear in native code.

bank identifiers are supplied manifest hashes. Prefer DIRECT references to compatible existing
fixtures. A new_fixtures entry is allowed where existing component data does not line up; preserve
all saved data unchanged. Mark synthetic inputs exploratory and cite source-backed behavior honestly.
Within new_fixtures, {$fixture:...,pointer:...} references other NEW fixtures only. Cross-bank use
is through ScenarioFixtureSelection, never a fabricated $fixture alias. You may reuse saved row
values in new coherent query definitions; explain that reuse in purpose. Do not copy unrelated banks.
Only literal 'generated' identifies the newly published bank. Never supply filesystem paths.

Resources must supply standard database queries: sql, parameters array, columns/rows for SELECT,
out_parameters indexed by the actual JDBC output indices for callable results, and optional prepared
SQLException. Database parameters must match the values the full XML entry will actually pass.
A missing-query failure is not a no-row answer. Do not replace business methods with mocks.
Use links for equal producer/consumer fixture values where possible (e.g. request's parsed data to
procedure parameters, procedure link IDs to lookup parameters). Do not assert equality across an
actual conversion; represent its correctly transformed value explicitly.

Each scenario must reference expected_xml prepared FROM SOURCE BEFORE execution. Cite exact excerpts
for the expected response and resource behavior in expectation_citations. This is not equivalence
proof. Never change an expected result just to match a failed native run.
For citation source_identity use ONLY an identity explicitly listed in original_evidence.sources or
native_sources. Never infer an identity from a component ID or an XML attribute. Copy literal excerpts.
Count actual expected JDBC executions in expected_resource_executions, including one lookup per row where needed.
Use at most comparison_case_limit cases, select one explicit scenario, and report genuine missing
evidence/capability in unresolved rather than inventing it. Fixture revisions and existing tests
cannot be overwritten, removed or weakened. Do not put credentials into fixtures or responses.
'''
