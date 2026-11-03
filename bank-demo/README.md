# Bank Demo — WSBCC Workspace

A realistic demo of a bank's IBM WebSphere Business Component Composer (WSBCC)
workspace. Used as a test fixture for the Composer Sunset migration pipeline.

## Fresh component-first acceptance run

From the repository root in PowerShell:

```powershell
$env:PYTHONPATH = 'source'
$env:PYTHONDONTWRITEBYTECODE = '1'
python -B -m tools.behavior_verification.component_pilot_run --output-root outputs/bank-demo-component-first-new
```

Use a new output folder and the configured model credential in the process environment.
This reruns the actual Mapper and converter in `component_first_v1` mode on the selected
bank-demo operations. It retains the 900000-character budget, both four-attempt limits,
automatic gates and the selected policy's technical checks. It does not deploy or perform Git actions.
Existing converter modes and saved runs are unchanged.

The wrapper writes `live-status.json`, `acceptance-report.md`, `cf8-measurement.json`,
request sizes in decimal KB/MB/GB, executor interaction/transport counts, and the existing
source-bound pilot measurement. Size checks include oversized probes never sent to the
model; they are not model-call counts or token counts. Components and preparation are
not accepted units. The selected `conversion_checklist_v1` policy requires bounded
source-checklist mappings, native API/configuration checks, compilation and executed JUnit
tests before operation assembly. Terminal conversion readiness checks those receipts and
transitive component/part manifests. Warm reuse is measured only after full cold acceptance.
Blocked runs retain their actual pending/failed/incomplete counts and causes.

Checklist mapping uses bounded batches, reports every detectable error in each batch,
retains valid sibling items, and corrects only unfinished IDs with precise feedback and
persistent retry limits. It establishes traceability, not Composer equivalence.
This policy does not prepare/run legacy code, approve individual library calls, generate
comparison inputs or execute comparison coverage/mutation checks. Normal dependency,
IBM-reference, reflection, native settings, routing, Spring wiring and JUnit checks remain.
Delivery reports distinguish `conversion_ready` from `production_ready`; original/native
behavioral equivalence is `not_assessed`, and production publication remains separately gated.
Historical standalone comparison experiments below require an explicit comparison policy.

The first CF8 run is under `outputs/bank-demo-component-first-20261027`. Its current
report is the evidence source; this paragraph does not assert bank or enterprise acceptance.

## Demo Framework Classes

The shared `WSBCC_XML/src` tree supplies `Context`, `CCOperationStep`, and
`HTTPService` for the demo operation steps. Bind the same `Context` to each step
with `setContext`; its `getValueAt` and `setValueAt` methods carry operation values.
Database steps require a JDBC connection supplied through `setConnection`.
The caller manages the connection and transactions.

For fraud detection, construct `HTTPService()` and register it
on the step with `setService("FraudDetectionService", service)`. It returns a fixed
sample XML response with score 7 and decision ALLOW, without network calls. These
classes implement the contracts used by this fixture.

Every formatter/decorator tag actually configured in the demo XML now has Java
source in `WSBCC_XML/src`, including `CCMandatory`, `CCNullToZero`, `CCConstant`,
and `CCSysTimeDate`. Shared format/decorator and operation support is supplied too;
the demo sources compile together without Composer binaries. Format children,
decorators, operation steps and format-role entries can be registered explicitly
by a fixture caller; this is a small demo runtime, not a replacement WAS server.
The existing tag registry also lists unused Composer types; these are not part of
the configured demo and are not implementations supplied to conversion units.

The fixture's explicit policies are: `CCMandatory` rejects null/empty values in
both directions, while `CCNullToZero` changes null/empty to `"0"` in both directions;
neither trims whitespace. Decorators run forward on output and in reverse on input.
For example, the configured account-number input strips padding before checking
mandatory, so an all-zero account number is rejected. `CCConstant` outputs its
configured value and ignores input. `CCSysTimeDate` deliberately outputs the fixed
epoch timestamp `1970-01-01T00:00:00Z`; `CCTime` retains its fixed demo time.
These are test contracts, not claims about proprietary Composer implementations.

The shared formatter support executes decorator chains, XML escaping, runtime
attribute decoration (including the source-defined conditional `xsi:nil`), child
formats, and the demo's named-XML collection rows. Indexed collection items are
maps; each row inherits runtime settings and the caller's JDBC connection without
overwriting the parent values. Database formatters still require caller-supplied
JDBC connections. No placeholder `UnsupportedOperationException` remains in the
demo Java sources.

`source/tests/test_bank_demo_source_completeness.py` checks configured tag/step
source coverage, compiles all demo Java, executes decorator and format behavior,
and runs fresh Mapper/preparation to verify that implementing/decorator/helper
sources reach unit extraction evidence. Missing sources must be implemented or
their XML usage removed, rather than inferred from a tag name or a manual table.
Fresh mapping/intake is required after these source changes; prior accepted facts
and generated output do not establish acceptance of this revised demo.

## Channels

### Scoped converter validation

Use `bank-demo/scoped_converter_validation.yaml` from the repository root for a fresh scoped intake. It selects explicit Java projects for INTERNET, IVR, and XML. The demo `.classpath` files declare INTERNET's XML dependency and IVR's XML/INTERNET dependencies (the latter supplies the common operation helpers). This is Java source visibility, not permission to resolve XML definitions from arbitrary channels.

Operation contexts are declared once in each channel's `defaultFile/dsecontext.xml`; operation files reference those contexts. Error-body switches name the actual shared `StandardErrorRSFmt` definition. The registered service/connector documents exist: shared services and connector pools are empty, while INTERNET registers the existing dummy `FraudDetectionService`. Its implementation still returns the documented fixed response and makes no external network call. JDBC connections remain caller-supplied.

C7 verifies preparation of all 10 operation contexts. Native generation, compilation of converted output, behavior equivalence, and final approval remain C8/C9 work. Existing runs predate changed source/layout/policy evidence: regenerate into a fresh run instead of resuming their checkpoints.

| Workspace | Channel | Operations |
|---|---|---|
| `WSBCC_XML` | XML | None — shared base definitions only |
| `WSBCC_INTERNET` | INTERNET | GetClientAccountsOp, GetAccountDetailsOp, TransferFundsOp, GetClientLinksOp, ValidateClientLinksOp, GetClientOverviewOp, ClientCallFlowDemoOp |
| `WSBCC_IVR` | IVR | GetClientAccountsOp (IVR variant), GetAccountBalanceOp, ClientCallFlowDemoOp |

## Operation Summary

### GetClientLinksOp (INTERNET)
Simple linear operation. One DB opStep. Good as pilot example.
- 1 opStep + 3 error opSteps
- Shared format: StandardErrorRSFmt
- Context: GetClientLinksCtxt (parent: InternetBaseCtxt)

### GetClientAccountsOp (INTERNET + IVR)
Returns all accounts for a client. Exists in both channels with different
opStep sets and format structures. The IVR version uses PIN auth and returns
simpler data. Demonstrates: onlyFor filtering (LogIvrCall step).

### GetAccountDetailsOp (INTERNET)
Returns full account details + transactions. Demonstrates: multi-step linear
routing, CCKColl (balance block), CCIColl (transactions list), CCTableFormat
DB lookups, date range input.

### TransferFundsOp (INTERNET)
Most complex operation. Demonstrates: iniValue pre-population, multi-step
branching, onTimeoutDo routing, on{N}Return error body switching, MaskLogDecorator
on sensitive fields, fraud detection backend service call.

## Nested operation examples

`GetClientOverviewOp` calls both `ValidateClientLinksOp` and `GetClientLinksOp`.
`ValidateClientLinksOp` also calls `GetClientLinksOp`. All three use INTERNET.
The dependency-first waves are GetClientLinksOp (1), ValidateClientLinksOp (2),
and GetClientOverviewOp (3). The two new operations reuse the existing links
request/reply/error formats and context without changing the original operation.

The demo `com.ibm.il.dse.cc.cut.CCComplexOpStep` resolves the configured
`opExecuteName` through a registered operation executor, shares the caller context,
and propagates its return code. Native conversion replaces that dispatch with an
HTTP client. See [operation-call conversion](../docs/operation_calls.md).

## Repeated step labels and channel-specific calls

`ClientCallFlowDemoOp` is registered in both INTERNET and IVR. Its source XML in each channel contains three `CallClientOperation` occurrences, all implemented by `CCComplexOpStep`:

| Source order | Restriction | Called operation |
| --- | --- | --- |
| 1 | Unrestricted | `GetClientAccountsOp` in the consuming channel |
| 2 | `onlyFor="internet"` | `GetClientLinksOp` |
| 3 | `onlyFor="ivr"` | `GetAccountBalanceOp` |

Each channel therefore has two executable occurrences with the same ID and implementation but different `opExecuteName` values. The unrestricted call uses `on0Do="next"`, which advances to the applicable second occurrence after channel filtering. Both channel variants end after their call; unsuccessful calls end immediately. The unused variant remains in the scoped resource inventory. This covers repeated IDs in one effective flow, the same labels in different operations/channels, lowercase `onlyFor`, positional routing, and distinct operation-call dependencies.

The request contains `ClientId` and `SessionToken` for INTERNET, or `ClientId`, `AccountNumber`, and `Pin` for IVR. Credentials use the existing log-masking decorator. The example reuses `BaseOpCtxt`, defines its own simple request/reply formats, and retains `StandardErrorRSFmt`. Successful execution still requires the existing demo database/service dependencies of the called operations.

Expected scoped results:

- INTERNET calls `GetClientAccountsOp` then `GetClientLinksOp`.
- IVR calls `GetClientAccountsOp` then `GetAccountBalanceOp`.
- Both demo operation views have migration wave 2 and two distinct callees.
- Full-workspace discovery has 10 operation views and 7 call sites; the existing overview chain remains unchanged.

Use scoped output for these examples: legacy output cannot preserve repeated step labels reliably. They are converter acceptance inputs; full scoped conversion remains gated until the [converter implementation plan](../docs/plans/scoped_vault_converter_implementation_plan.md) is implemented. Adding these fixtures does not enable that conversion path.

## Shared Components

**Java classes used by multiple operations:**
- `MapErrorByValueAlways` — used by ALL operations for error handling
- `ValidateInputFields` — used by GetClientAccountsOp, GetAccountDetailsOp, TransferFundsOp

**Formats used by multiple operations:**
- `StandardErrorRSFmt` — csErrorReplyFormat for all operations

**Context hierarchy:**
```
nil
 └── BaseOpCtxt
      └── InternetBaseCtxt (INTERNET)
           ├── AccountOpCtxt
           │    ├── GetClientAccountsCtxt
           │    ├── GetAccountDetailsCtxt
           │    └── TransferFundsCtxt
           └── GetClientLinksCtxt
      └── IvrBaseCtxt (IVR)
           ├── GetClientAccountsCtxt
           └── GetAccountBalanceCtxt
```

## Running composer-mapper against this demo

The demo includes a thin `CCTime` formatter and a minimal `Tag` attribute holder.
`initializeFrom(Tag)` selects the configured `dataName`; `format(Context)` emits
that XML element with the fixed sample time `00:00:00`, and
`unformat(String, Context)` stores a dummy `Date(0)` in the named context field.
These are conversion fixtures for `ExecutionTime` and `TransactionTime`; production
time parsing, timezone conversion, and Reuters behavior are outside their scope.

```bash
java -jar composer-mapper.jar \
  --root  "path/to/bank-demo/composer/Workspace" \
  --vault "path/to/output/vault" \
  --vault-layout scoped \
  --workspace-id bank-demo \
  --md \
  --channel INTERNET
```

Expected scoped output with `--channel INTERNET`:
- 7 operation views, including `ClientCallFlowDemoOp`, under `channels/INTERNET/operations/`
- Separate occurrence notes for the demo's two applicable `CallClientOperation` steps
- 5 operation-call sites, including the original three-call overview chain
- Channel resource inventory, `vault-manifest.json`, and resolution diagnostics

Omit `--channel INTERNET` to generate both channel examples: 10 operation views and 7 call sites. Use a new or empty destination. Existing ambiguous context declarations in other demo operations remain reported separately; the new call-flow examples do not resolve or suppress those diagnostics.


### Decorator source evidence

The XML-channel `NilDecorator` is an executable attribute-decorator example, not a
universal null-to-XML rule. Its superclass `AttributeXmlFormatDecoratorImpl` and
`SchemaValidationSettings` are supplied Java dependencies. The demo boundary takes
the decorated field's already formatted string; it does not recreate the full
Composer `DataElement`/`FormatElement` runtime.

At runtime it reads `CHANNEL_NAME` and `APPLICATION` from `Context`. It adds
`xsi:nil="true"` only for a configured validation channel, a non-excluded application,
and a null or zero-length formatted value. Whitespace is not empty. Missing/invalid
context values are logged and leave the attribute map empty. Configuration initially
enables no channels; `SchemaValidationSettings.configure` takes lowercase channel and
application names. There is no value conversion or unformat override in this decorator.

Conversion must follow the mapped class, parent and supporting sources and preserve
these conditions as typed native inputs/configuration collaborators. Generated tests
must cover both outcomes; the tag name alone cannot establish an expected nil attribute.
Changes to this source require fresh Mapper intake and preparation, not reuse of the
old C9 source fingerprints. This example does not establish full bank-demo acceptance.
## Isolated thin-path experiment

Run just `GetClientLinksRQFmt`, `StandardErrorRSFmt`, and `NoLinksFound` from an existing
bank-demo run, using a **new** experiment output directory:

```powershell
$env:PYTHONPATH = "source"
python -B -m tools.behavior_verification.thin_path_run --input-run outputs/single-operation-source-validation-smoke-20261029/run/single-get-client-links --output outputs/bank-thin-path-experiment-20261029
```

This experiment generates each configured unit directly from its XML and complete selected
Java evidence. It does not schedule framework classes separately or require AI checklist
citations. Parser data still generates cases and identifies runtime settings. Generated code
must pass source/API safeguards, actual Maven/JUnit execution, and isolated original/native
boundary comparison. Failed comparisons return concrete inputs and observations to the bounded
correction loop; the experiment stops on the first exhausted failure.

`thin-path-status.json` records progress. Each attempt retains build evidence and a
`comparison/boundary-comparison.json` with outputs, differences, and coverage gaps. A
`matched_observed_cases` result describes only these three boundaries on observed samples;
it is neither exhaustive equivalence nor acceptance of the operation, stored procedure,
complete bank demo, or production deployment. The original run database is opened read-only;
all experiment state is separate. The normal converter's gates remain unchanged.

### Getter binding and comparison limitations

Request output binding now inspects compiled public getters. Matching case-folds names and
ignores separators, requires exactly one compatible getter chain, and retains XML parent
paths for repeated field names. If distinct XML paths cannot be associated with distinct
legacy context keys, the experiment reports a limitation instead of guessing. Scalar types
come from actual legacy observations; unknown/incompatible types remain incomplete.

DTOs must expose explicit boolean presence accessors (`hasField` or `wasFieldSet`, for
example). A null getter value is never evidence that a write occurred. Without presence
information, observable values may still be compared, but presence remains unverified.
Legacy exceptions with partial writes are labelled `partial_writes_not_compared`; matching
exception types alone cannot make those cases pass. Independent later cases still execute.
Tool/API/environment limitations stop AI correction. Only concrete compared-value differences
return concise input/expected/actual feedback, without probe/checklist inventories.

Replay the retained third candidate without regenerating its Java (use a fresh output path):

```powershell
python -B -m tools.behavior_verification.thin_path_run --input-run outputs/single-operation-source-validation-smoke-20261029/run/single-get-client-links --output outputs/bank-thin-path-attempt3-replay-20261029 --replay-database outputs/bank-thin-path-experiment-20261029-v2/experiment.db --replay-attempt 3 --replay-unit GetClientLinksRQFmt
```

Replay records the original response/source hashes, reruns compilation/tests/comparison,
and retains every candidate and comparison attempt. It never substitutes the most recent
failed candidate or writes production acceptance records.
