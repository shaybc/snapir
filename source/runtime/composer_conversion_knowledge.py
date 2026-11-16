"""Embedded Composer behavior shared by all conversion prompts.

Snapshot of the developer manual runtime, context, format, and decorator sections.
Runtime conversion does not read the manual; update this module when behavior changes.
"""

COMPOSER_BEHAVIOR_SECTIONS = (
    ('4. Runtime Execution Model', r'''## 4. Runtime Execution Model

### High-Level Flow

When a channel handler receives an HTTP/service request for operation `GetClientLinksOp`:

```
1. Channel Handler receives request XML
2. Looks up "GetClientLinksOp" in dse.ini selfDefOper → finds XML file path
3. Loads and initializes CCDSEServerOperation from that XML file
4. Channel Handler calls: operation.unformat(requestXml)
   → request format cascades through the fmtDef structure
   → each formatter tag reads its value from the XML and writes it to context
   → each decorator in the chain transforms the value before/after the formatter
5. Channel Handler calls: operation.execute()
   → opStep chain runs according to RC routing
   → opSteps read from / write to context
6. Channel Handler calls: operation.format()
   → response format cascades through the reply fmtDef
   → each formatter tag reads its value from context and builds XML output
   → each decorator transforms the value
7. Channel Handler returns the formatted XML response
```

**Important:** Steps 4, 5, and 6 are managed by the channel handler infrastructure. The developer defines what happens inside each step, not the orchestration between them.

### CCDSEServerOperation.execute() — The opStep Loop

The execute() method runs the opStep chain:

```java
// Pseudocode of CCDSEServerOperation.execute()
public void execute() throws Exception {
    // 1. Set channel context values
    setValueAt("HOST_HEADER.HOST_KEY", getHostKey());
    setFields(getOperationfields());

    // 2. Filter opSteps not applicable to this channel
    removeOpStepsNotForThisChannel();

    // 3. Run the opStep chain
    int index = 0;
    KeyedCollection end_opstep = null;
    if (isFinallyOpStepExist()) {
        end_opstep = getFinallyOpStep();  // the "End" step if defined
    }

    do {
        KeyedCollection kc = getOperationStep(index);
        index = processOpStep(kc, operationName, index);
    } while (index != -1);

    // 4. Run the "End" step if it exists
    if (end_opstep != null) {
        processOpStep(end_opstep, operationName, index);
    }

    // 5. Error body substitution (if an opStep switched the reply format)
    if (isReturnedErrorBodyChanged() && getReturnedErrorBodyChanger() != null) {
        // substitute csErrorReplyFormat for csReplyFormat
    }
}
```

### processOpStep() — RC Routing

The RC routing priority for each opStep result:

```
1. Check "on{RC}Return" → if set, switch the error reply format body
2. If RC == RC_TIMEOUT → check "onTimeoutDo" first
3. Check "on{RC}Do" → if found, go to that step name
4. Check "onOtherDo" → if found, go to that step name
5. Check "onOtherDoDefault" → if found, use it (with warning log)
6. If next == "next" → increment index, continue loop
7. If next == "end"  → return -1, break loop
8. Otherwise → look up step by name, jump to it
```

### Channel Filtering — onlyFor

Before execute() runs, `removeOpStepsNotForThisChannel()` scans all opSteps and removes any that have an `onlyFor` attribute whose value does not match the current channel name.

```xml
<!-- This step only runs on the INTERNET channel -->
<opStep id="InternetOnlyValidation"
        implClass="operations.InternetValidation"
        onlyFor="internet"
        on0Do="end"
        onOtherDo="OperationFailed"/>
```

**Conversion rule:** When converting an operation XML to native code for a specific channel, opSteps with `onlyFor` values that do not match the target channel are simply omitted from the generated code. The generated class reflects only the steps that actually run for that channel.

---'''),
    ('5. Context', r'''## 5. Context

### What Context Is

The context is a hierarchical runtime data store. It is the central communication mechanism between all components of an operation — formatters read from and write to it, opSteps read from and write to it, decorators do not directly access it (they transform string values, not context fields).

At runtime, the context is essentially a nested map:
```
context["ClientId"]      = "123456"
context["ClientName"]    = "John Doe"
context["links"]         = [list of link objects]
context["ERROR_CODE"]    = "10"
context["ERROR_NUMBER"]  = "0"
```

In practice, any Java object can be stored in a context field — strings, numbers, collections, custom objects. The formatter tags define how those objects are serialized to/from XML.

### Context Inheritance Chain

Contexts form an inheritance hierarchy via the `parent` attribute:

```xml
<context id="BaseOpCtxt"     parent="nil"         type="op"/>
<context id="InternetCtxt"   parent="BaseOpCtxt"  type="op"/>
<context id="GetLinksCtxt"   parent="InternetCtxt" type="op"/>
```

When `GetLinksCtxt` is active:
- An opStep or formatter can read/write fields in `GetLinksCtxt`
- It can also read/write fields in `InternetCtxt` (parent)
- It can also read/write fields in `BaseOpCtxt` (grandparent)
- Each context has its **own isolated namespace** — there is no collision between field names in different levels
- Access traverses up the chain: if a field is not found in the current context, the runtime looks in the parent, then grandparent, up to `nil`

### Context Access Rules

- **Formatters** (CCString, CCDate, CCXML, etc.): read from and write to context fields identified by their `dataName` attribute
- **opStep implClasses**: have full access to the context chain — can read any field and write any field at any level they have access to
- **Decorators**: do NOT directly access context — they receive a string value from the formatter and return a transformed string
- **No component can access context fields from a sibling context** — only from its own context and its ancestors

### Context in the Operation XML

```xml
<context id="GetLinksCtxt" parent="nil" type="op"/>

<CCDSEServerOperation id="GetLinksOp" operationContext="GetLinksCtxt">
    ...
</CCDSEServerOperation>
```

The `operationContext` attribute binds the operation to its context. The context is instantiated once when the operation starts and lives until the operation completes.

---'''),
    ('6. Formats and the Format/Unformat Process', r'''## 6. Formats and the Format/Unformat Process

### What a Format Is

A `fmtDef` is a declarative description of an XML data structure. It is not a DTO class — it is a recursive tree of formatter tags, each of which knows how to:
- **unformat**: read its value from incoming XML and write it to the context
- **format**: read its value from context and write it to the output XML

The format tree is walked recursively. Each node in the tree is a formatter tag instance.

### Format and Unformat Direction

**Unformat (parsing — XML → context):**
```
Incoming XML string
  → root formatter tag's unformat() is called
  → root tag parses its children recursively
  → each leaf formatter reads its XML element value
  → (if decorators present: removeDecoration() chain applied first)
  → final value written to context[dataName]
```

**Format (serializing — context → XML):**
```
context[dataName] value
  → (if decorators present: addDecoration() chain applied first)
  → leaf formatter writes its value as an XML element
  → parent formatters build the XML structure up the tree
  → result is the complete XML output string
```

### Decorator Chain Direction

**During unformat (parsing incoming XML):**
```
XML string value
  → last decorator in chain: removeDecoration(value)
  → second-to-last decorator: removeDecoration(previous result)
  → ... (chain runs in reverse order)
  → first decorator: removeDecoration(...)
  → result passed to formatter for context write
```

**During format (building outgoing XML):**
```
context value (string from formatter)
  → first decorator in chain: addDecoration(value)
  → second decorator: addDecoration(previous result)
  → ... (chain runs in forward order)
  → last decorator: addDecoration(...)
  → result written to XML output
```

The decorator chain is defined by the order of decorator tags after the formatter tag in the XML.

### Format Execution Contexts

The format/unformat process is not limited to request/response. It occurs whenever data needs to be serialized or deserialized:

- **Request reception**: channel handler calls unformat on `csRequestFormat`
- **Response building**: channel handler calls format on `csReplyFormat` (or `csErrorReplyFormat` if error body was switched)
- **Backend request**: an opStep builds a request to a backend system using a format
- **Backend response**: an opStep parses a response from a backend system using a format
- **Logging**: some opSteps serialize context data to log using a format

### refFormat — Format Reuse

```xml
<!-- In CCDSEServerOperation: -->
<refFormat name="csRequestFormat"  refid="GetLinksRQFmt"/>
<refFormat name="csReplyFormat"    refid="GetLinksRSFmt"/>
<refFormat name="csErrorReplyFormat" refid="StandardErrorFmt"/>
```

The `name` attribute is the role the format plays in this operation. The conventional names are:
- `csRequestFormat` — the incoming request XML structure
- `csReplyFormat` — the success response XML structure
- `csErrorReplyFormat` — the error response XML structure (substituted when an opStep signals an error body change via `on{RC}Return`)

The `refid` points to a `fmtDef` id, which may be defined in the same XML file, in `dseformat.xml`, or in any other file loaded via `defaultFile`.

### CCTableFormat — Database Lookup During Format

`CCTableFormat` is a special formatter that performs a database lookup during the format process. When the format tree reaches a `CCTableFormat` node during format (building outgoing XML):
1. It reads the key value from context (identified by `keyValue` attribute)
2. Queries `fromTable` column `fromColumn` where the key matches
3. Writes the result as the field's XML value

This means database calls can happen during response building, not just during opStep execution.

---'''),
    ('7. Decorators', r'''## 7. Decorators

### What a Decorator Is

A decorator follows a formatter tag. Its implementation determines whether it transforms a value, adds attributes, or reads runtime context/configuration. Supplied implementation and transitive Java source evidence determine behavior; the examples below explain architecture, not fixed replacement rules. Preserve source-dependent runtime conditions as typed native inputs or collaborators. Missing behavioral evidence must be reported, not inferred from a tag name.

**XML syntax:**
```xml
<CCString dataName="AccountId"/>
<CCPadding padChar="0" length="9"/>
```

`CCPadding` is a decorator that follows `CCString`. The decorator tag appears as a sibling immediately after the formatter's self-closing tag.

### Decorator Contracts

There are two decorator base classes with different contracts:

**Type 1 — Value Decorator** (extends `FormatDecoratorHolder`):
```java
public String addDecoration(String s);     // called during FORMAT
public String removeDecoration(String s);  // called during UNFORMAT
public Object initializeFrom(Tag tag);     // reads this tag's own attributes
```

Example — `CCPadding`:
- `addDecoration("1234567")` → `"001234567"` (pad to length 9 with '0')
- `removeDecoration("001234567")` → `"1234567"` (strip leading zeros)

**Type 2 — Attribute Decorator** (extends `AttributeXmlFormatDecoratorImpl`):
```java
public Hashtable formatXmlAttributes(Context ctx, DataElement de, FormatElement fe);
public Object initializeFrom(Tag tag);
```

This type operates at the XML attribute level rather than the string value level. It can add XML attributes (like `xsi:nil="true"`) to the output element. Example: `NilDecorator`.

### Decorator Chain Rules

1. A decorator applies only to the immediately preceding formatter tag
2. Multiple decorators can be chained after one formatter — each receives the previous one's output
3. During **format**: chain runs in order (first decorator → last decorator)
4. During **unformat**: chain runs in reverse order (last decorator → first decorator)
5. `initializeFrom(Tag tag)` reads only this decorator's own XML attributes — never the formatter's attributes or sibling tags
6. A decorator can be placed after a complex formatter (like `CCXML`) — in that case it decorates the entire XML subtree produced by that formatter

### Example — Multiple Decorators

```xml
<CCString dataName="Amount"/>
<RemoveLeadingZerosDecorator/>
<CCPadding padChar=" " length="12"/>
```

**During unformat** (input XML: `<Amount>   0001234</Amount>`):
1. `CCPadding.removeDecoration("   0001234")` → strips right-padding → `"0001234"`
2. `RemoveLeadingZerosDecorator.removeDecoration("0001234")` → `"1234"`
3. `CCString` writes `"1234"` to context["Amount"]

**During format** (context["Amount"] = "1234"):
1. `CCString` reads `"1234"` from context
2. `RemoveLeadingZerosDecorator.addDecoration("1234")` → (no-op in format) → `"1234"`
3. `CCPadding.addDecoration("1234")` → `"        1234"` (12 chars, space-padded left)
4. XML output: `<Amount>        1234</Amount>`

### All Decorator Tags (from XML channel dse.ini)

| Tag | Class | Description |
|---|---|---|
| `nilDecorator` | `...decorator.NilDecorator` | Attribute behavior and runtime conditions must be derived from supplied Java source |
| `RemoveLeadingZerosDecorator` | `...decorator.RemoveLeadingZerosDecorator` | Strips leading zeros |
| `CCPadding` | `...decorator.CCPadding` | Pads string to fixed length |
| `CCFixedLength` | `...decorator.CCFixedLength` | Enforces fixed string length |
| `CCMandatory` | `...decorator.CCMandatory` | Validates field is not empty |
| `CCNotNull` | `...decorator.CCNotNull` | Validates field is not null |
| `CCZeroToNull` | `...decorator.CCZeroToNull` | Converts zero value to null |
| `CCNullToZero` | `...decorator.CCNullToZero` | Converts null to zero |
| `fZeroToDecimalIDB` | `...decorator.ZeroToDecimalIDB` | Handles zero decimal display |
| `fFixedLengthTranIDB` | `...decorator.FixedLengthTranIDB` | Fixed-length transform |
| `fStringDateIDB` | `...decorator.StringDateIDB` | String-to-date conversion |
| `fZeroToNullIDB` | `...decorator.ZeroToNullIDB` | Zero-to-null for IDB |
| `fTrimIDB` | `...decorator.TrimIDB` | Trim whitespace for IDB |
| `SmartMirror` | `...decorator.SmartMirror` | Hebrew/Latin text mirroring |
| `HebrewWHF` | `...decorator.HebrewWHF` | Hebrew character handling |
| `MF2Hebrew` | `...decorator.MF2Hebrew` | Mainframe-to-Hebrew conversion |
| `Base64Decorator` | `...decorator.Base64Decorator` | Base64 encode/decode |
| `ArithmaticAction` | `...decorator.ArithmaticAction` | Arithmetic on value |
| `CCRegExp` | `...decorator.CCRegExp` | Regex validation |
| `CCRegExpReplace` | `...decorator.CCRegExpReplace` | Regex replace |
| `MaskLogDecorator` | `...decorator.MaskLogDecorator` | Masks value in logs |
| `TypeReceive` | `...decorator.TypeReceive` | Type conversion on receive |
| `SetCenturyFor2DigitsYear` | `...decorator.SetCenturyFor2DigitsYear` | Y2K year handling |
| `CCPhoneNumberDecorator` | `...decorator.CCPhoneNumberDecorator` | Phone number formatting |
| `AltamiraChannelDecorator` | `...decorator.AltamiraChannelDecorator` | Altamira channel transform |
| `HebrewLogicalToVisualDecorator` | `...decorator.HebrewLogicalToVisualDecorator` | Hebrew visual order |
| `unicodeDecorator` | `...decorator.UnicodeDecorator` | Unicode handling |
| `convertReservedTags` | `...decorator.ConvertReservedTags` | XML reserved char escaping |
| `delimS` | `...decorator.DelimiterStr` | Delimiter-based splitting |

---'''),
)
