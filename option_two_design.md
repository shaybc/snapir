# Option two design

Status: the configured behavior-unit pipeline is implemented as an opt-in strategy.
The operation-to-operation workflow below is an agreed design revision and is not
yet fully implemented; the existing strategy status does not imply its completion.
Its development stages are in the [staged implementation plan](docs/plans/operation_conversion_workflow_implementation_plan.md).
The implementation record is in [option_two_implementation_plan.md](C:/GitHub/shaybc/snapir/option_two_implementation_plan.md).
Live migration pilots and production-equivalence evidence remain required.

The option-one implementation is preserved by the Git tag `option1_stable`.

## Agreed base plan

These are the per-operation conversion steps implemented by `behavior_units`.
The job-level scope, approval and execution requirements below govern when each
operation may enter these steps.

1. **Identify and map the operation:** discover its XML, referenced definitions,
   configured tags, implementing classes, and relevant supporting dependencies.
   Record how each source participates in the selected operation and channel.
2. **Separate the three parts:** request unformatting, configured op-step execution
   and routing, and response formatting, including the error response.
3. **Convert request unformatting:** supply the complete configured format and its
   relevant formatter/decorator source to the model. Generate Jackson wire models
   and native post-parsing mapping methods that preserve the established input
   conversions and produce agreed business inputs.
4. **Convert response formatting:** supply the response format and supporting
   implementations. Generate business-result-to-wire mapping methods, the required
   output conversions/decorations, and Jackson models for XML serialization.
5. **Convert execution incrementally:** take each configured op-step, its XML
   attributes, and relevant implementation/dependency evidence separately. Generate
   a native Java business class or method, with helpers where needed, suitable for
   use inside the Spring microservice.
6. **Connect the units:** implement the operation flow as ordinary method calls
   and branches preserving routing, outcomes, and side effects. Expose it through a
   thin Spring endpoint, then validate the three parts and their integration.

Establish shared input/output and collaborator contracts before generating units
independently. Discovery can identify the complete dependency set without sending
the entire operation's source stack in one model request. Supply bounded evidence
for each unit and carry accepted contracts forward.

## Operation dependencies and approved sequential conversion

This workflow applies to the complete requested job, including a channel or an
explicit operation selection. It is not limited to pilot selection. The detailed
rules are in [Calls between Composer operations](docs/operation_calls.md).

1. **Check the whole dependency scope inside intake.** Resolve each CCComplex call, including
   indirect calls and targets outside the selected channel or operation list.
   Every target must be included with its required evidence or have a trusted,
   successfully converted API record in the database, including previous jobs.
   Show the existing services that will be reused. Block on missing or ambiguous
   dependencies, show the required operations and call paths, and ask the user to
   include or resolve them. Do not generate placeholders or null-return substitutes.
2. **Block cycles.** Display the complete operation-call cycle and supporting
   evidence, ask the user to resolve it or correct the mapping, and replan. Cycles
   are not automatically assigned a conversion order or converted as one service.
3. **Present intake's plan for approval.** After scope resolution, show dependency-first waves,
   explicit operation order, prerequisites and reused API contracts for the entire
   conversion run. Any pilot follows the same dependencies. Intake produces this
   plan as its final user-facing output. Approve it once before the thin wrapper,
   using existing approval machinery and a separately saved run-plan policy.
   Default to human review; automatic/skip settings affect only the human pause.
   Save the accepted scope, graph, order, contracts and approval evidence, and
   obtain renewed acceptance after material changes.
4. **Finish each operation.** Execute the existing per-operation conversion,
   assembly, service generation, packaging, tests, validation and required review
   gates. Publish its complete reusable API contract and completion checkpoint
   only after those checks pass. Then start the next operation. For A calling B
   calling C, C completes first, then B, then A; do not generate every caller's
   units first or defer packaging until a whole batch finishes.

The new thin sequential wrapper invokes the existing conversion workflow; it does
not replace or duplicate it. Select one operation from the accepted plan, provide
its resolved dependency contracts, invoke the current workflow through completion,
publish its service record/checkpoint, then advance. Keep existing conversion,
generation, assembly, packaging, test, review and bounded-correction behavior;
adapt only the entry points needed to run that workflow for the current operation.

Apply the existing four gates per operation with their current numbers and
configurable human/automatic/skip policies. They follow the separate run-plan
approval after intake; the run-plan approval is not repeated for every operation.
Reuse the existing decision machinery, with evidence identifying the operation
and gate and referencing the accepted plan. All-human settings can require four
approvals per operation in addition to the single plan approval. Users control
the human pauses through settings; failed technical/dependency checks still
block. Pause the wrapper at a pending/rejected gate and retain the current
operation for Resume. No duplicate conversion or approval engine is required.

A CCComplex step identifies an operation call, not a request to reproduce the
Composer dispatcher. Convert it into an HTTP client using the completed target's
published request, response and error contract. Preserve the caller's data and
routing semantics. Store the supported media types and address configuration;
initial transport remains XML, with JSON contracts recorded only when supported.

Trust a successfully converted API record when building its callers. Planned
interfaces and assembled-only records are not completed services. The publishing
operation owns full validation; a later caller uses that record without repeating
the target's conversion checks. Registry access must work across jobs. Keep
readiness separate from API identity, and apply existing invalidation rules only
to actual relevant changes rather than ordinary reuse.
Treat a trusted published service as a satisfied boundary, without reopening its
internal conversion dependency tree for the new caller.

### Two database roles

Keep one database per run for its scope, approved plan, progress, drafts,
validation evidence and checkpoints. Add one persistent shared registry database
for the migrated source application, outside its individual run folders. All of
that application's channels, modules and later runs consult the same registry.

The shared database maps each successfully converted source operation to its
microservice and saved call contract: source application/channel/operation, API
revision, service identity, inputs, outputs, errors, method/route and address
configuration, including environment-specific URL/port values when known. An
optional Swagger/OpenAPI link accompanies, rather than replaces, the saved API
definition. Draft or incomplete records do not qualify as converted services.

A run records the shared API identity, revision and contract/address data it uses
inside its own existing database. This API-use snapshot is a record, not another
database. It keeps Resume tied to the contract used by that run. On successful
completion, publish the service in the shared registry and save its reference and
completion checkpoint in the run database before advancing. Later runs reuse the
shared record without merging old run databases or revalidating the target.

### Existing conversion and validation behavior

Reuse the existing operation tests, generation-correction limits and validation
policies. The current microservice remains the input/output/error acceptance
boundary, including its service dependencies. This revision adds no separate
whole-job chain-testing stage and does not decide mock/runtime-test configuration.
Automated tests of the new wrapper happen during development, not as another
stage inside each conversion run.
On failure, stop at the current operation and retain completed work for Resume.
Conversion readiness and later Composer retirement remain separate decisions.

## Discovery and evidence mapping

Begin from the selected operation, not arbitrary source classes. Resolve its
request, success, and error formats; contexts; configured op-steps; formatter and
decorator mappings; and recursive Java dependencies. Preserve configured attribute
values and channel-specific applicability alongside the implementing source.

Classify each dependency as available application source, a retained external
library, or removed Composer runtime behavior explained by the central embedded
knowledge. Unavailable product source is not itself a requirement to recreate the
product. Missing application evidence and unresolved behavior remain visible.

The mapping supports assembling the format and op-step input bundles described
below. Its class list is an evidence inventory, not a required list of native
output classes.

## Goal

Convert the business behavior of a Composer operation into a modern Java Spring
microservice. Remove the Composer runtime dependency without rebuilding its
context engine, op-step router, formatter hierarchy, or decorator holders.

Use the original application Java, operation XML, configured attributes, and
embedded Composer semantics as evidence. Do not assume every legacy class needs
a corresponding generated class. Do not use previously generated option-one code
as the authority for original behavior.

## Three parts of an operation

1. **Request unformatting:** read the incoming message, apply the configured
   conversions and decorator removal, and produce typed business inputs.
2. **Execution:** run the configured business steps and routing, carrying explicit
   inputs, outputs, outcomes, and integration dependencies.
3. **Response formatting:** take the operation results, apply configured output
   conversions and decorators, and serialize the expected response structure.

Composer uses context to connect these parts. The native implementation uses
agreed request models, result models, local values, and method contracts instead
of a generic context replacement.

## Target service structure

The service contains a thin Spring controller, request/response wire models,
explicit mapping code, a business service expressing the operation flow, and
local or shared business collaborators. Database and HTTP integrations can remain
separate collaborators where useful for testing and reuse.

Initial input and output support is XML. Eventual JSON support is required, using
the same business service and typed business contracts. Detailed XML-to-JSON rules
for names, collections, attributes, numbers, absent values, and nulls remain future
work; do not infer them automatically from a convenient serialization default.

## XML binding decision

Use Jackson XML for the initial direction. Generate ordinary Java wire models
with explicit XML root, element, attribute, nesting, and collection mappings.
Spring's XML message converter can deserialize request bodies and serialize
response bodies using those mappings.

Jackson performs structural mapping. It does not infer Composer transformations
from formatter names or XML configuration. Root naming annotations also do not
by themselves prove validation of the incoming root element. Required structure,
validation, and lexical rules need explicit implementation and tests.

An XSD may be an additional structural artifact where useful. It is not a required
starting point, and it cannot replace the transformation contract.

## Complete-format conversion task

Treat a configured format as one conversion unit rather than independently
converting every formatter or decorator tag.

### Input bundle

- The format XML and referenced nested format definitions.
- Resolved formatter and decorator implementation source, including relevant
  supporting classes and methods.
- The actual configured attributes and channel/operation usage.
- Central embedded Composer behavior, including format direction and decorator
  execution order.
- The agreed typed business input or output contract.
- Available examples and explicit unresolved behavior questions.

Resolve the complete relevant evidence set, but feed large dependency stacks in
bounded requests. Never silently truncate source. Summaries should retain source
identity and hashes so subsequent requests can inspect the necessary details.

### Output bundle

- Jackson-mapped wire models and supporting nested types as needed.
- Request mapping methods that produce typed business inputs.
- Response mapping methods that produce the correct wire values.
- Helpers only where justified by repeated behavior.
- Tests for representative XML, transformed values, and errors.
- Structured artifact metadata, interfaces, evidence references, and unresolved
  questions for later scheduling and review.

Generate only the direction required by the selected use, or both directions when
the format is used for both. This is one logical converter action, although it may
require several internal analysis and generation requests.

### Request flow

```text
Request XML
  -> Jackson deserialization
  -> wire request object
  -> generated request mapping and validation
  -> typed business input
  -> operation business service
```

Keep raw text where needed to preserve meaningful distinctions before conversion.
The mapper need not mutate the wire object. It can produce a separate business
object containing the transformed values.

### Response flow

```text
Operation business result
  -> generated response mapping and output transformations
  -> wire response object
  -> Jackson serialization
  -> response XML
```

Map the error response as well as the success response. Preserve the operation's
error-body selection and established error category/number values.

### Transformation rules

Implement ordinary Java transformations derived from the supplied source and
configuration. Preserve decorator order for each direction, value conversion,
padding, precision, null/empty/absent behavior, and error behavior where established.

Do not replace those rules with a generic Composer interpreter. Reusable helpers
may implement a defined transformation, but should not recreate the legacy tag
execution framework.

For example, dividing numeric input by one hundred is correct only if the actual
input formatter defines two implied decimal places. A decimal-places attribute
alone may control output presentation and is insufficient evidence for scaling.

Demo stubs and dummy outputs do not establish production behavior. Record the
specific affected rule as unresolved rather than copying the stub or inventing a
default. Distinguish known structure from uncertain edge behavior.

## Configured op-step conversion task

Treat an op-step's configured behavior as a conversion unit. Supply its original
implementation, relevant dependency code, XML attributes, Composer semantics,
and the agreed data contracts.

Extract what the step reads, writes, calculates, calls, and returns. Generate an
ordinary Java class or method with explicit inputs, outputs, external collaborators,
and outcomes. Preserve observable side effects and error behavior.

Small helpers can be merged into the unit. Database and HTTP access can remain
separate adapters. Do not force every dependency into one class or convert each
legacy dependency independently simply because it is a class.

The operation service connects the generated units using explicit branches derived
from the configured routing. It does not run a reflection-based op-step engine.

## Contracts and local/shared placement

Agree on data and method contracts before generating units independently. This
prevents one unit from inventing a context setter or collaborator method that
another unit does not provide.

Confirm local versus shared placement from the resulting behavior, interface,
configuration requirements, and actual consumer needs before final integration.
The same original class name alone does not prove that two configured uses can
share a native implementation. Preserve library boundaries for ordinary retained
dependencies and remove Composer runtime dependencies.

Retain `shared_library_min_usage` and `broad_library_usage_threshold`. Count distinct
channel-qualified operation consumers, not repeated references within one operation.
Apply placement to a **complete format definition** (including its referenced
structure and transformations) or a **configured op-step behavior unit**. Do not
independently place formatter/decorator tags or nested sub-format fragments into
shared libraries. A nested definition used separately as a complete operation
request or response can be a complete-format unit in that separate use.

Group compatible behavior and contracts first; count consumers within that group.
Below the minimum threshold, generate locally. At or above the minimum, assign a
shared library; above the broad-sharing threshold, use the common library, following
the existing grouping convention. Include direction and configured transformations
in format compatibility. Configuration differences must be either compatible
explicit parameters of the shared API or separate behavior groups. Do not merge
incompatible uses merely to reach a threshold.

## Model requests and persisted output

Use bounded source analysis followed by generation for each configured behavior
unit. Save accepted analysis and contracts so later requests do not need the
entire source tree. A whole-service architecture invention request is not the
primary conversion mechanism for this revised direction.

Production agents exchange validated JSON contracts for artifacts, methods,
dependencies, requirements, evidence, and unresolved questions. Markdown is the
human-readable report of those contracts, not the authoritative scheduling input.

## Validation

- Validate model response JSON and schemas.
- Check generated artifacts against agreed interfaces and dependency contracts.
- Reject retained Composer runtime references before accepting code.
- Compile and provide targeted compiler feedback with bounded corrections.
- Test XML mapping and format transformations separately from business steps.
- Test operation routing, integration calls, side effects, and error responses.
- Preserve human review and approval evidence for accepted behavior and artifacts.

Compilation is necessary but does not prove business equivalence. Where original
runtime captures or fixtures are available, use them for comparison. Otherwise
state the limits of evidence-based validation.

## Next small steps

1. Choose one request format from the Internet Transfer operation.
2. Build its exact XML/source/configuration evidence bundle.
3. Agree on its wire model and business-input contract.
4. Run a format-only generation experiment for Jackson models and mapping methods.
5. Check representative parsing and transformation results.
6. Repeat for success/error responses, then one configured op-step.
7. Integrate the proven contracts into the operation service.

The earlier design-only pilot is reference material:
`docs/experiments/option_two_transfer_funds_design.md`. This document records the
subsequent, narrower direction: three operation parts and configured behavior-unit
conversion rather than unrestricted whole-operation design.

## Open work

- Define the machine-readable format-task and op-step-task schemas.
- Decide the precise division between deterministic XML model generation and
  model-assisted generation of custom transformations.
- Establish nested structures, attributes, repeated elements, and optional-value
  contracts for the pilot.
- Resolve only concrete missing behavior; do not require exhaustive manual
  documentation of every property.
- Map this revised direction onto checkpoints, gates, reports, reuse identities,
  and native artifact ownership before implementation.

This document records design decisions; the revised operation-dependency workflow
still requires implementation. Documentation changes do not change application
code, existing runs, configuration or previously generated output.
