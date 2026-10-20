# Bank Demo — WSBCC Workspace

A realistic demo of a bank's IBM WebSphere Business Component Composer (WSBCC)
workspace. Used as a test fixture for the Composer Sunset migration pipeline.

## Demo Framework Classes

The shared `WSBCC_XML/src` tree supplies `Context`, `CCOperationStep`, and
`HTTPService` for the demo operation steps. Bind the same `Context` to each step
with `setContext`; its `getValueAt` and `setValueAt` methods carry operation values.
Database steps require a JDBC connection supplied through `setConnection`.
The caller manages the connection and transactions.

For fraud detection, construct `HTTPService()` and register it
on the step with `setService("FraudDetectionService", service)`. It returns a fixed
sample XML response with score 7 and decision ALLOW, without network calls. These
classes implement the contracts used by this fixture. Other Composer format and
server framework types still require their own implementations.

## Channels

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
