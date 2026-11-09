"""Keep AI-selected target behavior distinct from full supporting-source evidence."""

INSTRUCTION = '''Convert only behavior required by the selected operation/configured component and its selected consumers.
Supporting sources may contain unrelated methods, imports and library references; their presence is not an obligation
to convert them or to declare their libraries in the native output. Read the complete supplied evidence and decide
which behavior is required. Omit unrelated code and dependencies, but preserve required construction, initialization,
cleanup, errors, side-effect ordering and runtime-dependent branches. Never discard required behavior merely to
avoid a dependency. Do not mechanically reproduce entire helper classes or Composer parent frameworks.
Retain ordinary third-party APIs instead of reimplementing Oracle, tracing SDKs or other vendors. Use only verified
retained library candidates when needed; a candidate inventory is availability, not a required dependency list.
Composer contracts come from the documentation and available source; report a specific material gap only when both
are insufficient. Other IBM client APIs require the supplied exact approvals; Composer runtime is never retained.
Declare only dependencies actually used by the chosen main/test code, with their correct scopes.
Keep source-oracle and test-only dependencies separate from the shipped native runtime.
Compilation, executed tests/mocks and behavior review still decide acceptance; a scope claim is not proof.
'''
