# Option two pilot: TransferFunds native service design

Design only; 8 October 2026. No application code, build, provider call, deployment, commit, or push was requested or performed.

## Scope and evidence discipline

The sole retained artifact is this report. The selected operation is INTERNET / TransferFundsOp in [internet_transfer.yaml](/C:/GitHub/shaybc/snapir/configs/internet_transfer.yaml). The target is Java 25 with Spring; a Spring release and dependency versions remain implementation-time decisions. This design does not claim to have verified any particular Spring release's Java 25 support.

Analysis started with the original operation XML, resolved channel imports and formats, inspected the inventory resolver, and then read the relevant implementation method groups and their immediate runtime dependencies. Generated option-one Java, vault notes, and migration planning reports were not used as behavioral evidence. The source inventory was rebuilt in memory and filtered to TransferFundsOp: 61 configured uses, 16 distinct resolved implementations, and four missing CCMandatory uses. The inventory performs static source-type analysis; it does not prove reflective dispatch, overload resolution, or runtime behavior. An initial dependency print was too broad; subsequent interpretation used operation-filtered bindings and original source reads. No inventory output artifact was saved.

No filesystem AGENTS.md was found in the repository search; the human-provided AGENTS instructions apply. Minimal change plan: create only this report to describe the selected operation and proposed native design; leave application code, source XML, configuration, existing generated work, and unrelated behavior untouched.

Evidence labels below mean: **configured** = original XML attributes; **implemented** = executable statements in original Java; **knowledge** = embedded Composer interpretation; **proposal** = native architecture; **decision** = requires human or production evidence. A fixture or stub cannot prove production equivalence.

## Source register and compact component index

| ID | Original source and relevant group | Evidence role |
|---|---|---|
| E1 | [TransferFunds.xml](</C:/GitHub/shaybc/snapir/bank-demo/composer/Workspace/WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/selfDefOper/TransferFunds.xml>) — operation, both local formats, local context | Wire tree, step routing, constants |
| E2 | [INTERNET dse.ini](</C:/GitHub/shaybc/snapir/bank-demo/composer/Workspace/WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/dse.ini>) and [XML dse.ini](</C:/GitHub/shaybc/snapir/bank-demo/composer/Workspace/WSBCC_XML/src/Xml Definition/Channel/XML/dse.ini>) | Registry, import XML, tag ownership |
| E3 | [XML shared formats](</C:/GitHub/shaybc/snapir/bank-demo/composer/Workspace/WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dseformat.xml>) — StandardErrorRSFmt | Error body |
| E4 | [INTERNET contexts](</C:/GitHub/shaybc/snapir/bank-demo/composer/Workspace/WSBCC_INTERNET/src/Xml Definition/Channel/INTERNET/defaultFile/dsecontext.xml>) and [XML contexts](</C:/GitHub/shaybc/snapir/bank-demo/composer/Workspace/WSBCC_XML/src/Xml Definition/Channel/XML/defaultFile/dsecontext.xml>) | Parent resolution |
| E5 | [ValidateInputFields.java](/C:/GitHub/shaybc/snapir/bank-demo/composer/Workspace/WSBCC_INTERNET/src/com/ibm/il/dse/operations/common/ValidateInputFields.java) — execute | Presence check |
| E6 | [ValidateTransferLimitsSP.java](/C:/GitHub/shaybc/snapir/bank-demo/composer/Workspace/WSBCC_INTERNET/src/com/ibm/il/dse/operations/internet/db/ValidateTransferLimitsSP.java) — execute | Limits JDBC contract |
| E7 | [CallFraudDetection.java](/C:/GitHub/shaybc/snapir/bank-demo/composer/Workspace/WSBCC_INTERNET/src/com/ibm/il/dse/operations/internet/service/CallFraudDetection.java) — execute, buildFraudRequest, parseFraudScore, parseFraudDecision | Fraud payload, response handling, timeout |
| E8 | [ExecuteTransferSP.java](/C:/GitHub/shaybc/snapir/bank-demo/composer/Workspace/WSBCC_INTERNET/src/com/ibm/il/dse/operations/internet/db/ExecuteTransferSP.java) — execute | Transfer JDBC contract and output order |
| E9 | [MapErrorByValueAlways.java](/C:/GitHub/shaybc/snapir/bank-demo/composer/Workspace/WSBCC_INTERNET/src/com/ibm/il/dse/operations/common/MapErrorByValueAlways.java) and [SetChannelContext.java](/C:/GitHub/shaybc/snapir/bank-demo/composer/Workspace/WSBCC_INTERNET/src/com/ibm/il/dse/operations/common/SetChannelContext.java) | Error descriptions and timeout flag |
| E10 | [Embedded knowledge](/C:/GitHub/shaybc/snapir/source/runtime/composer_conversion_knowledge.py) — sections 4–7 | Routing priority, format direction, context inheritance, decorators |
| E11 | [Inventory resolver](/C:/GitHub/shaybc/snapir/source/tools/component_inventory_tools/inventory.py) and [channel mappings](/C:/GitHub/shaybc/snapir/source/tools/component_inventory_tools/channel_mappings.py) | Provenance and scoped reference resolution |
| E12 | [Context.java](/C:/GitHub/shaybc/snapir/bank-demo/composer/Workspace/WSBCC_XML/src/com/ibm/dse/base/Context.java), [CCOperationStep.java](/C:/GitHub/shaybc/snapir/bank-demo/composer/Workspace/WSBCC_XML/src/com/ibm/dse/base/CCOperationStep.java), [CCDSEServerOperation.java](/C:/GitHub/shaybc/snapir/bank-demo/composer/Workspace/WSBCC_XML/src/com/ibm/il/dse/cc/cut/CCDSEServerOperation.java) | Demo connection/service registration; framework stubs |
| E13 | [HTTPService.java](/C:/GitHub/shaybc/snapir/bank-demo/composer/Workspace/WSBCC_XML/src/com/ibm/il/dse/cc/service/communication/http/HTTPService.java) | Explicit dummy fraud service |

All formatter and decorator FQCNs below inherit the XML-channel mappings, even though INTERNET consumes them. Formatter prefix is `com.ibm.il.dse.cc.format`; decorator prefix is `com.ibm.il.dse.cc.decorator`.

| Configured component | Binding / dependency | Relevant methods read |
|---|---|---|
| CCDSEServerOperation | `com.ibm.il.dse.cc.cut.CCDSEServerOperation` → DSEServerOperation, Context, Tag, KeyedCollection | execute; routing helpers are stubs |
| ValidateTransfer | common.ValidateInputFields → CCOperationStep, Context | execute |
| CheckLimits | internet.db.ValidateTransferLimitsSP → CCOperationStep, Context, BigDecimal, JDBC | execute |
| FraudCheck | internet.service.CallFraudDetection → CCOperationStep, Context, HTTPService, BigDecimal | execute + three private helpers |
| SkipFraudOnTimeout | common.SetChannelContext → CCOperationStep, Context | setters, execute |
| ExecuteTransfer | internet.db.ExecuteTransferSP → CCOperationStep, Context, BigDecimal, JDBC, Date | execute |
| Nine error steps | common.MapErrorByValueAlways → CCOperationStep, Context | execute, description lookup |
| CCXML / CCString | XML-owned classes → AbstractFormatElement, Context, Tag | initializeFrom, format, unformat; private helpers stubbed |
| NumberFormat / CCDate / CCBoolean | XML-owned classes → Context, Tag; BigDecimal / SimpleDateFormat | initializeFrom, format, unformat |
| CCTime | XML-owned explicit fixture → Context, Tag, Date | initializeFrom, format, unformat |
| CCPadding / nilDecorator / MaskLogDecorator | CCPadding / NilDecorator / MaskLogDecorator → FormatDecoratorHolder, Tag where needed | initializeFrom and transformation methods |
| CCMandatory | mapped FQCN exists in dse.ini, Java source absent | Knowledge only; exact failure contract unresolved |

The package prefix for business opSteps is `com.ibm.il.dse.operations`. StandardErrorRSFmt resolves through the XML import, not the INTERNET shared-format file. That INTERNET file contains unrelated account/link formats; none is referenced by TransferFunds. No CCTableFormat or format-time database lookup belongs to this operation.

Context chain is TransferFundsCtxt → AccountOpCtxt → InternetBaseCtxt → BaseOpCtxt → nil. TransferFundsCtxt appears both locally and in INTERNET defaults with the same parent; inventory prefers the local definition. ErrorCtxt is a sibling, not an ancestor. Error fields are written into the active operation context, not accessed through ErrorCtxt. The flat-map demo Context does not implement the hierarchy described by E10; inheritance semantics require runtime evidence. None of the definitions declares a field-level authentication population contract.

## Preliminary architecture from operation XML

Purpose: receive a funds-transfer request, check required values and source-account limits, consult fraud detection, then execute the transfer through core banking. A fraud timeout permits execution with a response warning flag. Business failures use the shared XML error body.

Proposed boundary: XML endpoint → typed TransferFundsRequest → TransferFundsService → TransferLimits and FraudAssessment and TransferExecution ports → JDBC/HTTP adapters. The service returns a typed success or failure; XML rendering applies the existing field layout and confirmed transformations. One explicit method expresses the sequence. No Context hierarchy, reflection-based opStep router, decorator inheritance, generic formatter interpreter, or one native class per legacy class is proposed. JSON later supplies another transport adapter to the same request/use case.

At this stage the XML comments suggested amount validation, fraud score thresholds, and scheduled execution. Source reconciliation below removes those unsupported inferences.

## Exact configured XML structure and reconciliation

These are format trees, not a complete XSD or proof of all runtime lexical rules. No namespace, service URL, HTTP verb, request envelope, response status code, content type, XML declaration, or channel authentication contract is specified by E1. The enclosing `<XML>` in the definition file is configuration, not a request wrapper. Preserve case and direct-child nesting and declared output order. Input order enforcement, unknown fields, duplicate elements, and namespace acceptance remain decisions requiring captures/runtime evidence.

### Request: TransferFundsRQFmt

Root `<TransferFunds>` has these direct children in declared order:

| Field | Configured type / decorators | Implemented or known receive behavior |
|---|---|---|
| SourceAccount | CCString; CCMandatory; CCPadding zero length 10 | Padding removal runs before mandatory. Default left-padding removal strips leading zero characters. All-zero values can become empty. No maximum-length enforcement in CCPadding. |
| TargetAccount | Same as SourceAccount | Same transformations |
| Amount | NumberFormat; CCMandatory; no thousands separator; decimals enabled | Nonblank text has commas removed, then BigDecimal conversion. Blank becomes null after decorators if they allow it. Positivity, scale, and upper bounds are not checked by E5. |
| Currency | CCString; CCPadding space length 3 | Required by E5, though no CCMandatory decorator. Actual CCPadding initialization ignores a blank `padChar=" "`, leaving default **zero**, so source implementation strips leading zeros instead of spaces. This contradicts declarative intent. |
| SessionToken | CCString; CCMandatory; MaskLogDecorator | Mask remove is a no-op. Token must be nonblank; no authentication check is present here. Masking is delegated to an absent logging subsystem. |
| TransferReference | CCString; nilDecorator | Optional/nil intent. Demo removeDecoration(null) returns empty string, not null. Distinguish absent, nil, empty until runtime contract is settled. |
| ScheduledDate | CCString; nilDecorator | Optional opaque string, not a date formatter. No inspected business method reads it. Do not introduce scheduling. |

Decorator receive order is reverse: for accounts, padding removal then mandatory; for SessionToken, masking pass-through then mandatory. Send order is forward. Attribute processing for `xsi:nil` is not executable in the supplied formatter stubs. E10 describes NilDecorator as an attribute decorator; supplied NilDecorator extends the value-decorator base and returns null on blank output. Its comment claims nil handling that the supplied surrounding code cannot demonstrate.

Illustrative structure only (not a canonical lexical fixture):

```xml
<TransferFunds>
  <SourceAccount>0000012345</SourceAccount>
  <TargetAccount>0000067890</TargetAccount>
  <Amount>125.50</Amount>
  <Currency>ILS</Currency>
  <SessionToken>token</SessionToken>
  <TransferReference>reference</TransferReference>
  <ScheduledDate>20261009</ScheduledDate>
</TransferFunds>
```

### Success: TransferFundsRSFmt

Root `<TransferFundsResponse>` has direct children, in order:

| Field | Source / configured serialization |
|---|---|
| TransferId | Execute SP OUT 7; CCString |
| TransferStatus | Initially PENDING; success path overwrites with OUT 8, including null; CCString |
| ExecutionDate | OUT 9 java.sql.Date; CCDate pattern yyyyMMdd, useSep=no, fourDigYear=yes |
| ExecutionTime | Local new java.util.Date captured after date assignment; CCTime |
| Amount | Parsed request BigDecimal; NumberFormat, thousands=no, decimals=yes |
| Currency | Request currency; CCString + CCPadding length 3, intended space but actual initialization retains zero |
| SourceAccount | Transformed request string; CCString + zero-padding length 10 |
| TargetAccount | Same as source |
| NewSourceBalance | OUT 10 BigDecimal; NumberFormat + nilDecorator |
| FraudCheckSkipped | CCBoolean: true for Boolean.TRUE or case-insensitive string true; otherwise false, including absent |

CCDate formats Date values through SimpleDateFormat with the JVM default timezone; it passes non-Date values through as strings and emits an empty element for null. useSep/fourDigYear flags are read but do not alter the format method beyond its configured pattern. CCTime is explicitly a deterministic dummy that always renders `00:00:00`; that value is **not** a production contract. NumberFormat declares default decimalPlaces=2 but formatNumber is unimplemented: rounding mode, scale, decimal lexical rules and locale cannot be asserted. A null numeric value bypasses decorators and emits an empty element in the fixture; this conflicts with nil intent for NewSourceBalance. CCString helpers are stubs; null/escaping behavior is not established.

### Error: StandardErrorRSFmt

Root `<ErrorReply>` has direct children in order: `ErrorCategory` (string), `ErrorNumber` (string), `ErrorDescription` (string with nilDecorator), `RequestId` (string). No nested header or success fields are configured. RequestId is absent from TransferFunds request; provenance must come from channel/ancestor metadata and remains unresolved. No HTTP status mapping is evidenced. Error descriptions below are the demo lookup strings, not a verified production catalog.

## Reconciled routing and business behavior

| Stage / result | Next effect / terminal category, number | Demo error description |
|---|---|---|
| Presence validation 0 | Check limits | — |
| Presence validation any other RC (implemented 1) | 10, 2 | Validation failed: required field missing or invalid |
| Limits 0 | Fraud check | — |
| Limits 3 | 40, 3 | Daily transfer limit exceeded |
| Limits 4 | 40, 4 | Insufficient funds |
| Limits 5 | 40, 5 | Account not eligible for this operation |
| Limits 8 | 99, 8 | Technical error: database connection failure |
| Limits other RC | 99, 0 | Technical error: unexpected system failure |
| Fraud 0 | Execute transfer | — |
| Fraud 2 | 50, 2 | Transfer blocked: fraud risk detected |
| Fraud timeout -99 | Set FraudCheckSkipped to string true, then execute | — |
| Fraud any other RC, including service error 8 | 99, 0 | Technical error: unexpected system failure |
| Timeout-flag step 0 | Execute transfer | — |
| Timeout-flag step other RC | 99, 0 | Technical error: unexpected system failure |
| Execution 0 | End, normal reply | — |
| Execution 6 | 60, 6 | Core banking system rejected the request |
| Execution 7 | 60, 7 | Transfer already processed |
| Execution 8 | 99, 8 | Technical error: database connection failure |
| Execution other RC | 99, 0 | Technical error: unexpected system failure |

All nine error mappers write category, number, description and return 0; `on0Return="ErrorBody"` selects the error reply before `onOtherDo="end"` terminates. E10 routing precedence is return-body change, timeout branch, exact RC branch, fallback. There are no onlyFor branches or finally/End step in E1. Native terminal results encode this behavior directly.

Important qualifications:

- E5 checks SourceAccount, TargetAccount, Amount, Currency, SessionToken in that order using null/isBlank on String.valueOf; records the first failed name. Despite the XML comment, it never validates positive amounts. Do not add Bean Validation constraints that change this behavior without a decision.
- E6 returns success for any nonnull SP result other than the three recognized failures. A null result triggers switch failure inside the try and becomes DB error 8. Currency is mentioned in comments but never read or bound.
- E7 blocks only for the exact case-sensitive `<Decision>BLOCK</Decision>` substring. A score of 70 or 100 with ALLOW does not block; the threshold comment has no implementation. Score defaults to zero when tags are absent. Invalid score text can throw after the HTTP try; this is not returned as RC 8 by that catch. A null response also fails outside it. Malformed/missing decision silently becomes ALLOW in the demo parser. Replacing this with a strict parser changes edge behavior and needs a decision.
- Service lookup, context reads/casts, and request building occur before the HTTP try. Missing service registration and some setup failures escape rather than return 8. Timeout is specifically TimeoutException from call; other exceptions return 8 and therefore 99/0, not 99/8.
- E8 accepts every SP result except exact REJECTED and DUPLICATE, including null, as success. It does not consume SessionToken, FraudScore, FraudDecision, ClientId, or ScheduledDate despite comments suggesting some of these inputs.
- Context acquisition, casts, and getConnection occur outside each DB try. Missing connection/setup failures are not proven to map to 99/8. Prepare/bind/execute/output-read/statement-close failures inside try do map to RC 8. Channel handling of escaped exceptions and request-unformat errors is missing; do not silently convert all exceptions to an invented standard error.

## Data flow, external contracts, and side-effect order

Known sequence: channel unformats request → operation constants/initial values available → required-field check → limits SP → fraud call → optional skipped marker → execution SP → output assignments → success or error formatting. E10 supplies the host metadata behavior (`HOST_HEADER.HOST_KEY=TRFR`); E1 configures `CHANNEL_ID=INTERNET`, `MAX_RETRY=3`, TransferStatus=PENDING, FraudScore=0. No inspected Java implements retrying; MAX_RETRY must not become an automatic retry policy.

ClientId is read by limits and fraud but is not in the request format. RequestId appears in the error format but is likewise absent. Model these as explicit invocation metadata, supplied by a channel/authentication integration whose provenance must be confirmed. Preserve token confidentiality while determining whether the external channel already validates it. No new authentication semantics are inferred.

### Limits database boundary (E6)

Call exactly `{call PKG_TRANSFERS.VALIDATE_LIMITS(?,?,?,?,?,?)}`:

| Position | Direction/type | Value |
|---|---|---|
| 1 | IN string | SourceAccount after unformat |
| 2 | IN BigDecimal | Amount |
| 3 | IN string | ClientId from invocation metadata |
| 4 | OUT VARCHAR | SP result code |
| 5 | OUT NUMERIC | DailyRemaining, read only on LIMIT_EXCEEDED |
| 6 | OUT NUMERIC | DailyLimit, read only on LIMIT_EXCEEDED |

LIMIT_EXCEEDED → 3, INSUFFICIENT → 4, NOT_ELIGIBLE → 5, any other nonnull string → 0. Retain remaining/limit internally for parity and diagnostics; they are not response fields. Do not add Currency to the procedure arguments.

### Fraud boundary (E7)

Named service `FraudDetectionService`, call timeout exactly 5000 ms. Payload root FraudCheckRequest with direct children ClientId, SourceAccount, TargetAccount, Amount in that order. Currency and SessionToken are not sent. String concatenation uses Java string conversion (including null → literal null); BigDecimal textual scale is retained. The demo does not escape XML special characters. Production-safe XML generation is proposed only after a compatibility decision on special-character inputs; it must preserve ordinary payload values and order.

Response parsing consumes Score and the exact BLOCK decision string as above; preserves score and decision internally although neither goes to the execution SP or public reply. Do not introduce a score threshold, retries, fallback caching, asynchronous fraud, or a circuit-breaker fail-open rule that treats non-timeout errors as timeouts. HTTPService returns a fixed ALLOW/7 sample and ignores timeout; no URL, credentials, TLS, headers, HTTP status interpretation, real timeout mechanism, or service registry connector is provided. INTERNET dse.ini lists dseConnector.tmp, but that file is absent. A real transport contract requires additional evidence.

### Execution database boundary (E8)

Call exactly `{call PKG_TRANSFERS.EXECUTE_TRANSFER(?,?,?,?,?,?,?,?,?,?)}`:

| Position | Direction/type | Value |
|---|---|---|
| 1 | IN string | SourceAccount |
| 2 | IN string | TargetAccount |
| 3 | IN BigDecimal | Amount |
| 4 | IN string | Currency.trim() if nonnull, otherwise ILS |
| 5 | IN string | TransferReference, including unresolved empty/null distinction |
| 6 | OUT VARCHAR | SP result code |
| 7 | OUT VARCHAR | TransferId |
| 8 | OUT VARCHAR | TransferStatus |
| 9 | OUT DATE | ExecutionDate |
| 10 | OUT NUMERIC | NewSourceBalance |

REJECTED → 6; DUPLICATE → 7; all other codes including null → read outputs and return 0. Output read/write order is id, status, date, current local execution time, balance. Preserve the time-capture point through an injected Clock rather than substituting the procedure date/time or request ScheduledDate. A failure reading balance can occur after a database transfer and after time capture; it still becomes DB error in the source. Successful commit is not established by a return code alone. Retrying this ambiguous outcome can duplicate effects.

The two DB calls use the same externally supplied Context connection; CallableStatements close via try-with-resources, and neither operation closes, commits, or rolls back that connection. The Context comment assigns transaction ownership to its caller. The sequence can therefore hold a connection across fraud. No transaction isolation, auto-commit state, stored-procedure internal commits/locks, or rollback contract is present.

## Detailed proposed native design

One deployable transfer microservice, business package root `bank.transfers` (proposal; naming requires project agreement). Java records for immutable values, sealed result variants for explicit outcomes, BigDecimal for money, and ordinary methods for sequencing. Spring MVC XML handling is proposed for the synchronous operation; virtual-thread configuration and concurrency sizing are operational decisions after driver/client compatibility checks, not business changes.

| Proposed package / artifact | Method contract and responsibility |
|---|---|
| transport.xml.TransferFundsController | receive XML + external invocation metadata; decode, invoke TransferFundsService.transfer, render success/error XML. Route, HTTP verb/status remain decisions. No JDBC or fraud policy. |
| transport.xml.TransferFundsXmlCodec | decode(xml) → TransferFundsRequest or transport failure; encode(TransferOutcome, metadata) → XML. Owns exact roots/order, field lexemes, confirmed padding/nil/date/number rules. Does not expose generic formatter tags. |
| application.TransferFundsService | transfer(TransferFundsRequest, InvocationMetadata) → TransferOutcome; ordered presence validation, limits, fraud, timeout allowance, execute; explicit terminal outcomes. Framework-free logic. |
| model.TransferFundsRequest | String sourceAccount, targetAccount, currency, sessionToken; BigDecimal amount; presence-aware optional TransferReference and ScheduledDate. Represents post-receive values, not arbitrary Context keys. No XML/Spring annotations. |
| model.InvocationMetadata | ClientId, RequestId and confirmed channel/host metadata. Does not invent fields in request XML. |
| model.TransferOutcome | sealed Success(TransferReceipt), Failure(TransferFailure); escaped infrastructure/transport exceptions remain separate until their contract is confirmed. |
| model.TransferReceipt | id, status, executionDate, execution-time instant, amount, currency, source/target, optional balance, boolean fraudCheckSkipped. Date/time zone conversion decision remains at adapter boundary. |
| model.TransferFailure | Named reason + exact legacy category/number; internal diagnostic detail separated from public catalog description. |
| application.port.TransferLimits | check(LimitsInput) → Allowed / DailyLimitExceeded(remaining, limit) / InsufficientFunds / NotEligible / DatabaseFailure. Preserve raw SP result internally for unknown-code classification. |
| application.port.FraudAssessment | assess(FraudInput, timeout=5000ms) → Allowed(score, decision) / Blocked(score, decision) / TimedOut / ServiceFailure; parsing/setup failures use a distinct exception pending escaped-error decision. |
| application.port.TransferExecution | execute(ExecutionInput) → Executed(outputs) / Rejected / Duplicate / DatabaseFailure. Does not accept token, fraud score or scheduled date as procedure arguments. |
| adapter.jdbc.JdbcTransferGateway | Implements both DB ports; explicit ordinal binding/register/read helpers, statement closure, no schema redesign. Connection scope supplied by the agreed transaction/resource owner. |
| adapter.fraud.HttpFraudAssessment | Implements fraud port; request serializer, bounded synchronous call, specific timeout classification and approved parser behavior. No hardcoded dummy response. |
| transport.xml.LegacyTransferErrorCatalog | Formats approved descriptions for exact codes; initially traceable to E9 demo strings only. Could be a small static mapping rather than a general error framework. |
| configuration.TransferConfiguration | Spring bean wiring, datasource/client/Clock and confirmed connection scope; no business routing metadata interpreter. |

These are proposed responsibilities, not a command to create every listed file. Small records/result families may share a model file if project style permits; avoid cloning legacy artifacts. A dedicated validation class is unnecessary for a five-field ordered presence check. A generic context replacement map would defeat the design.

Dependency direction: XML controller and adapters depend on application/model contracts; application depends on model and its ports; model depends only on Java types. Spring, JDBC, HTTP, XML parsing, catalog serialization and logging integrations stay outside the business model. Spring wiring instantiates the service and adapters. Neither the domain nor service references Composer classes or XML field-tag classes.

Core flow contract in prose: validate post-decoding values in original required-field order; call limits once; stop on limits failure; call fraud once; stop on BLOCK/service failure; set skipped flag only for recognized timeout; execute once; stop on execution rejection/duplicate/database failure; build receipt from returned outputs and original transformed request values. Error category/number mappings are fixed as above. Initial PENDING and score zero are internal defaults, not fabricated successful receipt values. No parallelization changes this effect order.

Transport independence does not mean discard input distinctions: retain absent/nil/empty optional text until compatibility proves which distinctions may collapse. Keep account identifiers as strings. Keep ScheduledDate as text with no scheduling semantics. Do not put positive-amount checks or ISO currency constraints in record constructors. SessionToken should have a redacted toString/log policy; never use an autogenerated record dump in operation logging.

JSON is required eventually: add a JSON decoder/encoder calling the same typed use case, after deciding field names, absent/null semantics, decimal representation and date/time representation. Detailed XML-to-JSON mapping is intentionally future work. Do not infer a camelCase JSON contract or reuse XML wire strings as the domain's only representation.

## Transactions, resources and observability decisions

1. **Blocking decision:** obtain channel connection lifecycle and procedure specifications: shared transaction across both calls, locks held during fraud, internal procedure commits, rollback on business failure, isolation, connection release and pool limits. Until then, do not add @Transactional around the use case or split calls into independent transactions. A possible native request-scoped connection owner can preserve the same-session sequence, but lifecycle behavior cannot be chosen from the demo alone.
2. **Blocking decision:** confirm whether validation is a read, reservation or side-effecting procedure and how execution protects against balance changes between limits and transfer. Do not move validation after fraud or invent locking.
3. **Blocking decision:** duplicate/reference behavior, null/empty reference distinction, and recovery after commit followed by timeout/output/format failure. Do not retry based on MAX_RETRY=3 or add a new idempotency cache. DUPLICATE remains error 60/7.
4. **Decision:** production timeout definition and cancellation. Preserve 5000ms and only confirmed timeout fail-open behavior; classify connect/read/deadline conditions with evidence. No retry policy by default.
5. **Decision:** wire time format and zone; error catalog; XML nil/empty/escaping; numeric scale/rounding. CCTime and formatter stubs cannot settle these.
6. **Decision:** existing log/stat semantics for writeToLog=true and writeToOfecStat=true, host TRFR and channel INTERNET. Preserve the intent via explicit operation logging and metrics hooks once event shape/sinks are known. MaskLogDecorator itself does not mask anything; public logs must not expose token or unfiltered backend exception messages. This report does not remove telemetry or invent its production schema.

## Evidence gaps and human decisions

| Gap | Why it matters / needed evidence |
|---|---|
| Channel endpoint and envelope | Obtain handler configuration and representative raw XML/HTTP captures; do not append StandardRequestHeaderFmt or StandardReplyHeaderFmt because they merely exist in shared XML. |
| ClientId / RequestId provenance and token verification | Obtain authentication/session/channel setup; no business-class authorization logic is established. |
| CCMandatory and parse-error behavior | Obtain actual decorator/runtime error handling; parsing failures may occur before 10/2 presence routing. |
| CCPadding space bug | Human decides whether production implementation matches configured space intent or demo's zero default. Both behaviors documented; no silent correction. |
| NilDecorator mismatch / optional text | Obtain missing/nil/blank wire captures and actual formatter handling; empty vs null changes SP parameter 5. |
| NumberFormat helper missing | Obtain scale/rounding/locale and invalid-input behavior; default 2 in a field declaration is insufficient proof. |
| CCTime dummy; date zone | Obtain actual time formatter and environment settings; never freeze production time at 00:00:00. |
| Fraud demo parsing and dummy HTTP | Obtain real backend schema, transport settings and timeout/error captures; explicitly approve any parser hardening that changes malformed-response behavior. |
| Escaped failures | Obtain channel exception mapping before assigning HTTP status or 99/0 to them. |
| Catalog and observability | Obtain real descriptions, locale behavior, operation journal/stat events. |
| Duplicate context declaration | Confirm actual loader precedence/merge rules; definitions agree now but source inventory preference is not runtime proof. |

The design is suitable for review, not a declaration of production equivalence. The above blocking decisions prevent a faithful implementation from being completed using this bank-demo snapshot alone.

## Acceptance scenarios and equivalence evidence

Compilation alone is not equivalence. Future acceptance combines golden wire captures, ordered external-call traces, JDBC parameter assertions, return/error mappings and resource lifecycle tests. Demo-only behaviors must be marked as such and production decisions recorded separately.

| Scenario | Required observation |
|---|---|
| Normal transfer | Limits → fraud → execute once each; exact ordinals and payload; reply tree/order and confirmed lexemes match |
| Each required field null/blank | First failure in specified order; 10/2 if business validator reached; no external calls |
| Zero/negative amount | Presence validation alone accepts parsed value; downstream result controls outcome; no new positivity rule |
| Accounts zero-padded/all-zero/overlength | Leading-zero removal before mandatory; overlength not truncated; all-zero parse/validation outcome compared against runtime |
| Currency padded / leading zero / null | Compare confirmed padding implementation; execution trims nonnull; null ILS fallback tested at adapter level even if validator normally prevents it |
| Amount commas / exponent / excessive precision / invalid text | Evidence-supported parsing and exact output rounding; parse failure distinguished from business error |
| Each limits result | 3→40/3, 4→40/4, 5→40/5, 8→99/8; fraud/execution absent; unknown nonnull success; null DB error |
| Fraud ALLOW with high score | Execution proceeds; no invented >=70 rule |
| Fraud BLOCK with low score | 50/2; no execution |
| Fraud TimeoutException | Execute follows once; success flag true; no retry |
| Fraud other call exception | 99/0; no execution; flag remains false |
| Missing/invalid score, null or malformed response | Demo fallback/escaped cases explicitly compared and any approved production difference recorded |
| REJECTED / DUPLICATE | 60/6 / 60/7 error; success fields absent; no retry |
| Execution unknown/null result | Source semantics treat as success and read OUTs; no invented rejection |
| Null outputs / nil optional values | Exact nil, empty, absent representation established from production evidence |
| Statement execute/read/close failure | 99/8 only for caught DB failure; distinguish possible committed transfer and avoid retries |
| Missing connection or service | Escaped-failure channel behavior established; do not assume same mapping as caught failure |
| Clock/time boundary | SP date + local time capture point and confirmed timezone, independent of ScheduledDate |
| Resource trace | Same connection behavior, statement closure, commit/rollback/release match agreed ownership; no hold/release change hidden by mocks |
| Observability | Approved log/stat events retained, SessionToken masked, backend diagnostics kept out of public error description |
| Future JSON | Same business outcome and ordered calls as equivalent typed XML request; wire mapping separately approved |

Use real procedure integration in an authorized non-production environment to prove commits, duplicates, null behavior and locking; mocked JDBC cannot prove these. Use a controllable fraud server to exercise actual timeout classification. Those runs are future work; none was initiated here.

## Bounded artifact-by-artifact generation approach

Generation starts only after the human reviews this design and supplies/decides unresolved contracts. Each step receives the current approved contract plus a compact relevant evidence slice, not the entire workspace or option-one generated classes. Stop a slice when behavior lacks evidence; carry an explicit question rather than generate a TODO that pretends to preserve equivalence.

1. **Evidence contract artifact:** select E1/E2/E3/E4/E10 and operation-filtered inventory; record source hashes, XML selectors, method names, configured/implemented differences and decisions. Current report serves as the preliminary version. No application generation yet.
2. **Wire specification and capture matrix:** only E1/E3 and relevant formatter/decorator methods plus actual runtime captures. Resolve padding/nil/numbers/time/envelope/errors. Retain exact input/output and exception outcomes.
3. **Typed model and port contracts:** use reconciled field flow and E5–E8 argument/output groups. Review absent/null behavior, invocation metadata, result variants and dependency direction before implementations.
4. **Use-case artifact:** E1 routing + E5 validation + approved port contracts. Generate direct sequencing and terminal results; review every branch against the routing table. No Context/router scaffolding.
5. **Limits adapter:** E6 execute + approved connection contract only. Review six parameter positions, unknown/null SP code rules and exception scope.
6. **Execution adapter:** E8 execute + approved transaction/clock contract only. Review ten positions, output timing/order, null/unknown results and ambiguous execution failure.
7. **Fraud adapter:** E7 helper groups + real connector/protocol evidence. Review payload, exact timeout classification, parser decisions and service errors. E13 fixed ALLOW response is a test fixture only.
8. **XML adapter and catalog:** approved wire artifact + E9 and relevant formatting evidence. Review root/children/order, token logging, nil/empty, numbers/date/time and error-body selection. No generic format hierarchy.
9. **Spring wiring/build artifact:** approved adapter/resource decisions and verified Java-25-compatible dependencies. Generate minimal configuration only; do not infer production secrets/endpoints. Build commands require a later implementation task, not this report.
10. **Equivalence evidence artifact:** acceptance matrix with captures, call traces, resource outcomes and explicitly approved deviations. Build success is one check, never the sole acceptance criterion. JSON adapter follows as a separately approved wire-mapping artifact.

Selected prompt examples (descriptive only; no provider was called):

> Design-only intake: Read TransferFunds.xml and a compact inventory of its referenced components. Resolve imported tags and error format with provenance. Propose one business use case and transport/external boundaries. Do not write Java, load all classes, or consume option-one generated output. Label every inference.

> Reconcile DB boundary: Read only ValidateTransferLimitsSP.execute and ExecuteTransferSP.execute with their constants, plus the approved operation routing table. Report exact ordinal IN/OUT contracts, unknown/null return handling, caught versus escaped failures, output side-effect order and transaction questions. Do not invent parameters from comments.

> Reconcile fraud boundary: Read CallFraudDetection.execute/buildFraudRequest/parseFraudScore/parseFraudDecision and HTTPService. Separate fixture output from backend contract; retain 5000ms timeout fail-open routing, decision-based blocking and parser edge cases. Propose a typed port without cloning Composer service classes.

> Design wire model: Given only the operation format tree, relevant original formatter/decorator methods, embedded Composer chain semantics and approved captures, specify the XML adapter and transport-independent request. Identify disagreements such as space padding initialization, nil behavior and dummy time. Leave detailed JSON mapping for a later artifact.

> Future implementation gate: Generate only the single approved artifact named in the task, from the bounded evidence slice and approved method contracts. Return a traceability table and relevant acceptance checks. Stop and surface missing behavior; do not replace it with invented defaults, generic Context plumbing or compilation-only claims.

## Change record

Only `docs/experiments/option_two_transfer_funds_design.md` was created because a retained design report was explicitly authorized. Application code, original Composer XML/Java, config, generated option-one output, public APIs, routing, error numbers, timeout policy, SP signatures and side-effect order were not edited. No unrelated code changes were made. Read-only analysis and source-inventory inspection were performed; no application equivalence tests or build were run.
