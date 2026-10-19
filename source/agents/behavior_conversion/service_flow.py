"""Assemble approved native unit APIs using ordinary operation control flow."""

INSTRUCTION = """Return operation_contract with service_api, business request/success/error types, corresponding wire types and accepted unit contracts unchanged. Return this metadata with the service Java code, not as a separate planning response. Include newly required operation data sources in files.
Define and implement the native service API by connecting the accepted native units.
Generate direct Java calls and branches preserving the configured routing, timeout priority,
initial values, channel filtering, error-body switches, side-effect order and final steps.
Do not implement six Composer methods, a reflective router, or a generic Context engine.
Do not change accepted contracts or source files. Return one JSON bundle matching schema,
including executable operation tests covering every routing requirement in requirements.
Use exact dependency interfaces and supported behavior; flag unresolved evidence rather than
inventing defaults. Do not add a controller here; Spring wrappers are generated after review.
Use correction_feedback, behavior_review_feedback and final_validation_feedback to fix only the candidate service and tests. No prose or code fences."""
