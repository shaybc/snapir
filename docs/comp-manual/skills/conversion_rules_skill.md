# WSBCC Conversion Rules Skill

## Purpose

This skill defines the language-agnostic rules that govern how WSBCC XML operations
are converted to native microservice code in any target language. It applies to every
conversion agent regardless of target language (Java, Node.js, Python).

For language-specific code structure rules see:
- `skills/java_generation_skills/spring_boot_structure.md`
- `skills/nodejs_generation_skills/express_structure.md`
- `skills/python_generation_skills/fastapi_structure.md`

For full WSBCC source system knowledge see: `wsbcc_developer_manual_v2.md`

---

## Rule 1 — Evaluate, Don't Translate

The WSBCC XML is a declarative program. The generated code must be the **result of
evaluating that program** — not a reimplementation of the evaluation engine.

The generated microservice must never contain:
- A format engine or format tree walker
- A decorator chain executor
- A context hashtable
- An opStep dispatcher or RC router
- Any IBM WSBCC framework class or interface

```
WRONG: generate code that mirrors the XML structure
RIGHT: generate code that does what the XML describes
```

If converting the XML to code requires understanding what the XML means, that is correct.
If the generated code looks structurally similar to the XML, that is a signal something
is wrong.

---

## Rule 2 — Channel First

Every operation conversion is scoped to a specific channel. Establish the channel before
reading or converting anything else.

The channel determines:
- Which opSteps are included (those without `onlyFor`, plus those where `onlyFor`
  matches the target channel)
- Which tag→class mappings apply (from the channel's merged dse.ini)
- The operation name suffix if the same operation exists in multiple channels
  (e.g. `GetClientLinksOp` in INTERNET → `GetClientLinksService` in internet package;
  same operation in IVR → `GetClientLinksService` in ivr package)

opSteps with `onlyFor` values that do not include the target channel are **silently
omitted** from the generated code. Do not generate commented-out code for them.

---

## Rule 3 — Read the Java Source Before Converting Any opStep

The XML opStep tag tells you the class name. The Java source tells you what it actually
does. Never convert an opStep based on its name or attributes alone.

Before generating the equivalent native code for an opStep, read:
1. The implClass Java source — understand the business logic inside `execute()`
2. The return codes — understand what each integer means in this operation's context
3. The context reads and writes — understand what data flows in and out

The implClass Java source is the ground truth. The XML tag is just the pointer to it.

---

## Rule 4 — RC Routing Lives in the Operation XML

The opStep chain routing logic (`on{N}Do`, `onOtherDo`, `onTimeoutDo`, `on{N}Return`)
is defined in the **operation XML**, not in any Java class. The implClass only produces
a return code — it does not know what happens next.

When converting, read the operation XML's routing attributes to determine the complete
flow graph, then generate the equivalent imperative branching in the service layer.

```
XML: on0Do="end" on4Do="ErrorDataNotFound" onOtherDo="ErrorTechnical"

Generated:
  if rc == 0  → return success response
  if rc == 4  → throw DataNotFoundException
  else        → throw TechnicalException
```

---

## Rule 5 — Decorator Chains Are Value Transformations

Decorators are not a framework concept to be reimplemented — they are value
transformation functions to be inlined.

To convert a decorator chain:
1. Read the `addDecoration` method — this is the format (output) direction
2. Read the `removeDecoration` method — this is the unformat (input) direction
3. Generate equivalent transformation code directly in the serializer/deserializer

The direction matters: during unformat the chain runs in **reverse order**
(last decorator first). During format it runs in **forward order** (first decorator first).

```
XML:  <CCString dataName="AccountId"/>
      <RemoveLeadingZerosDecorator/>
      <CCPadding padChar="0" length="9"/>

Unformat (input parsing):
  String raw = xml.getAccountId();           // "001234567"
  raw = ccPadding.removeDecoration(raw);     // strip right-pad → "001234567" (no-op here)
  raw = removeLeadingZeros(raw);             // → "1234567"
  context.accountId = raw;

Format (output building):
  String val = context.accountId;            // "1234567"
  val = removeLeadingZeros.addDecoration(val); // (no-op in format direction)
  val = ccPadding.addDecoration(val);        // pad to 9 with '0' → "001234567"
  xml.setAccountId(val);
```

---

## Rule 6 — CCTableFormat Is a Service Concern, Not a Serializer Concern

`CCTableFormat` in a WSBCC fmtDef is a DB lookup that was incorrectly placed inside a
format definition. It is not a serialization rule — it is business logic that happens
to have been encoded as a format tag.

When you encounter `CCTableFormat` in a fmtDef:
1. Do not implement a DB call in the serializer/DTO class
2. Identify the lookup: table, column, key field
3. Add a repository method for that lookup
4. Call it in the service layer, before the response object is built
5. Populate the response DTO field with the result before serialization

The serializer/DTO class receives an already-populated value. It does not know or care
where that value came from.

---

## Rule 7 — Shared Components Are Converted Once

Any implClass, format structure, or utility that is used by more than one operation is
a shared component. It must be converted exactly once and placed in common-lib (or the
equivalent shared package for non-Java targets).

Do not convert the same implClass twice because two operations use it. Do not generate
two copies of the same DTO because two operations share a format structure.

Before converting any component, check the shared component registry. If it is already
there with a valid source hash, use the registered artifact. Do not regenerate.

---

## Rule 8 — Preserve Business Logic Exactly

When converting an IBM implClass to native code, the IBM framework plumbing must be
removed and the business logic must be preserved exactly as written.

IBM plumbing to remove:
- `import com.ibm.*` statements
- `extends CCOperationStep` / `extends AbstractDSEServerOperationIDB`
- `implements OperationStepInterface`
- `context.setValueAt(...)` → replace with typed field assignment
- `context.getValueAt(...)` → replace with typed field read
- IBM JDBC patterns (`context.getConnection()`) → replace with injected DataSource/JdbcTemplate
- `Trace.trace(...)` → replace with SLF4J logger

Business logic to preserve exactly:
- All conditional branches and their conditions
- All return code values and their meanings
- All arithmetic, string operations, date calculations
- All stored procedure names, parameter order, and column mappings
- All error category and error number values

If the business logic is unclear or ambiguous, flag it for human review rather than
guessing.

---

## Rule 9 — The Operation XML Is the Flow Spec; The Java Source Is the Logic Spec

These two documents together define the complete specification for one operation:

| Document | What it specifies |
|---|---|
| Operation XML | Which steps run, in what order, on which channels, with what routing |
| implClass Java source | What each step actually does — the business logic |

Neither document alone is sufficient. Generating from only the XML produces structure
without logic. Generating from only the Java produces logic without structure.

Both must be read and understood before generating the equivalent native code for any
operation.

---

## Rule 10 — Flag Ambiguity, Do Not Guess

If any of the following conditions are encountered during conversion, flag the item for
human review rather than proceeding with a guess:

- An implClass Java source file cannot be found
- A tag name cannot be resolved in the merged dse.ini
- A decorator's `removeDecoration` or `addDecoration` behavior is unclear from the source
- A return code is produced by an implClass but not handled by any `on{N}Do` attribute
- A `CCTableFormat` references a table or column that cannot be found in the DB schema
- The implClass source contains IBM framework calls whose native equivalent is not obvious
- The same operation name exists in multiple channels and the implementations differ
  in ways that suggest they should be one service, not two

Ambiguous conversions that proceed silently produce code that looks correct but behaves
incorrectly in production. A flagged item costs one human review. A silent mistake costs
a production incident.
