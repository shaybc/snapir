# Bank Demo — WSBCC Workspace

A realistic demo of a bank's IBM WebSphere Business Component Composer (WSBCC)
workspace. Used as a test fixture for the Composer Sunset migration pipeline.

## Channels

| Workspace | Channel | Operations |
|---|---|---|
| `WSBCC_XML` | XML | None — shared base definitions only |
| `WSBCC_INTERNET` | INTERNET | GetClientAccountsOp, GetAccountDetailsOp, TransferFundsOp, GetClientLinksOp |
| `WSBCC_IVR` | IVR | GetClientAccountsOp (IVR variant), GetAccountBalanceOp |

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

```bash
java -jar composer-mapper.jar \
  --root  "path/to/bank-demo/composer/Workspace" \
  --vault "path/to/output/vault" \
  --md \
  --channel INTERNET
```

Expected output:
- 4 operation notes (GetClientAccountsOp, GetAccountDetailsOp,
  TransferFundsOp, GetClientLinksOp)
- 17 opStep notes
- ~10 format notes
- 6 context notes
- ~12 Java class notes
- channels/INTERNET.md
- analysis/channel-operation-registry.md
