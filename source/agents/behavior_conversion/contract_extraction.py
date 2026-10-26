"""Extract explicit connection contracts before independently generating native units."""

INSTRUCTION = """Extract a reconciled typed Java operation contract from the supplied operation
XML, configured units, source evidence, routing and Composer semantics. Do not invent a new
business policy. Give each unit exact fully qualified native APIs and complete public method
declarations, including required construction/injection signatures. Put shared request/result/configuration/collaborator types in sources, as files
under src/main/java in the assigned contract packages. Use explicit typed data, not a Context
replacement or generic map. Use unit_data_packages for each unit's reusable data types;
reserve contract_package for operation-only types. Use unit_api_packages for implementation
APIs so unrelated operation types do not prevent reuse of compatible units. Keep sources
limited to complete business data/collaborator contracts that can compile before unit code.
Use sources to interpret the business behavior, not to preserve legacy class identities.
Read mapped implementations, superclasses and supporting sources before defining APIs.
Preserve source-dependent runtime context/configuration branches through explicit typed
inputs or collaborators in these contracts; do not replace them with tag-name assumptions
or conversion-time constants. Report missing behavior evidence as unresolved questions.
requirements map stable requirement IDs to evidence-backed behavior; evidence_ids identify
the supplied source or XML evidence. dependency_units contains only needed unit IDs and must
be acyclic. The service_api defines the operation's native service interface, including its
business input and success/error outcome contracts. request_type, success_type and error_type
are business types. request_wire_type, success_wire_type and error_wire_type identify the
Jackson XML types owned by the corresponding format units, not by sources. Include each
wire type in its unit's apis with no methods if it is a DTO. The Spring layer uses the request
mapper before the service and the response mapper afterward. Flag unresolved material behavior.
Use service_requirements to record evidence-backed operation-specific initialization, hooks,
cleanup and other behavior outside individual steps. Do not drop application operation code.
Return one valid JSON object matching schema, no prose. Verify JSON and required fields.
Do not return TODOs or assume dummy source outputs are production contracts."""
