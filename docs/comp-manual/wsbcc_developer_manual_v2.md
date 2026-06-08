# IBM WebSphere Server Business Component Composer (WSBCC) — Developer Manual v2

## Table of Contents

1. [Overview](#1-overview)
2. [Workspace and Channel Structure](#2-workspace-and-channel-structure)
3. [dse.ini — Configuration and Tag Registry](#3-dseini--configuration-and-tag-registry)
4. [Runtime Execution Model](#4-runtime-execution-model)
5. [Context](#5-context)
6. [Formats and the Format/Unformat Process](#6-formats-and-the-formatunformat-process)
7. [Decorators](#7-decorators)
8. [opSteps](#8-opsteps)
9. [CCDSEServerOperation](#9-ccdseserveroperation)
10. [XML Operation File Structure](#10-xml-operation-file-structure)
11. [Tag Reference](#11-tag-reference)
12. [Complete Operation Example](#12-complete-operation-example)
13. [Conversion Guide — WSBCC to Native Java](#13-conversion-guide--wsbcc-to-native-java)
14. [Best Practices](#14-best-practices)

---

## 1. Overview

IBM WebSphere Business Component Composer (WSBCC) is a configuration-driven service framework. Developers define service operations declaratively in XML files. The WSBCC runtime interprets those XML definitions to instantiate Java objects, execute business logic, parse incoming XML requests, build XML responses, and route execution based on return codes.

**The key insight for anyone reading this manual:** WSBCC is a runtime that executes a declarative XML program. The XML is not data — it is code. Every tag is an instruction to the runtime to instantiate a specific Java class, configure it with the tag's attributes, and execute it. Understanding this distinction is essential for both developing with WSBCC and for converting WSBCC operations to native code.

### Key Concepts

| Concept | Description |
|---|---|
| **Channel** | A deployment context (INTERNET, IVR, SME, etc.). Each channel has its own dse.ini, operation registry, and may override or extend shared operations. |
| **Operation** | A complete service unit. Defined in an XML file. Receives a request, executes a chain of opSteps, returns a response. |
| **opStep** | One step in an operation's execution chain. Maps to a Java class that performs a specific action (DB call, error mapping, data transformation, backend call). |
| **Format (fmtDef)** | A declarative description of an XML data structure. Drives serialization (format) and deserialization (unformat) of XML ↔ context data. |
| **Decorator** | A post-processor chained after a formatter tag. Transforms the formatter's string result in one or both directions (format/unformat). |
| **Context** | A runtime data carrier. A hierarchical map that holds all data flowing through an operation — request fields, backend results, computed values, error codes. |
| **dse.ini** | Per-channel XML configuration file that registers: the operation file list, all tag→Java class mappings, and service/processor definitions. |

---

## 2. Workspace and Channel Structure

### Workspace Layout

The WSBCC codebase is organized as a set of Eclipse workspaces, one per channel (plus shared/infrastructure workspaces):

```
composer/Workspace/
├── WSBCC_ARNAV/        ← ARNAV channel
├── WSBCC_BANKADMIN/    ← Bank Admin channel
├── WSBCC_COMMON/       ← Shared common library
├── WSBCC_EJB/          ← EJB infrastructure (not a channel)
├── WSBCC_G2/           ← G2 channel
├── WSBCC_GVP/          ← GVP channel
├── WSBCC_INTERNET/     ← Internet banking channel
├── WSBCC_IVR/          ← IVR (phone) channel
├── WSBCC_KIOSK/        ← Kiosk channel
├── WSBCC_MKT/          ← Marketing channel
├── WSBCC_ONLINEGOV/    ← Online government channel
├── WSBCC_SME/          ← SME (small business) channel
├── WSBCC_TRANSFERS/    ← Transfers channel
├── WSBCC_WEB/          ← Web channel
├── WSBCC_WS/           ← Web Services channel
├── WSBCC_WS_WAR/       ← Web Services WAR packaging
├── WSBCC_XML/          ← Common XML channel (shared definitions)
├── WSBCC_XML_EAR/      ← EAR packaging
└── WSBCC_XML_WAR/      ← WAR packaging
```

Each `WSBCC_{CHANNEL}` workspace contains:
```
WSBCC_{CHANNEL}/
└── src/
    └── Xml Definition/
        └── Channel/
            └── {CHANNEL}/
                ├── dse.ini                   ← Channel configuration
                ├── defaultFile/
                │   ├── dsecontext.xml        ← Context definitions
                │   ├── dseformat.xml         ← Format definitions
                │   ├── dsedata.xml           ← Data definitions
                │   ├── dseoperation.xml      ← Operation definitions
                │   └── dseConnector.tmp      ← Connector config
                └── selfDefOper/
                    └── *.xml                 ← Individual operation files
    └── com/...                               ← Java source files
```

### Channel Scope Rule

**Every operation belongs to a specific channel.** The channel's dse.ini is the authoritative registry for that channel's operations and tag→class mappings. When converting an operation to native code, the channel identity must be known because:

- Channel-specific opStep classes may differ from other channels
- `onlyFor` filtering of opSteps is resolved per channel
- The same operation name may exist in multiple channels with different implementations

**If the same operation name appears in multiple channel dse.ini files, they produce separate microservices** — e.g. `GetClientLinks_internet` and `GetClientLinks_ivr` — because the implementations may differ.

---

## 3. dse.ini — Configuration and Tag Registry

### Structure

The dse.ini is an XML configuration file. Its complete structure:

```xml
<?xml version="1.0" encoding="ISO-8859-1"?>
<dse.ini>

  <kColl id="import">
    <field id="sme"/>          <!-- imports another channel's dse.ini -->
  </kColl>

  <kColl id="settings">

    <kColl id="files">

      <kColl id="defaultFile">
        <!-- Root XML definition files loaded at startup -->
        <operDef id="Xml Definition/Channel/{CHANNEL}/defaultFile/dsecontext.xml"/>
        <operDef id="Xml Definition/Channel/{CHANNEL}/defaultFile/dseformat.xml"/>
        <operDef id="Xml Definition/Channel/{CHANNEL}/defaultFile/dseoperation.xml"/>
        <operDef id="Xml Definition/Channel/{CHANNEL}/defaultFile/dseConnector.tmp"/>
        <operDef id="Xml Definition/Channel/{CHANNEL}/defaultFile/dsedata.xml"/>
      </kColl>

      <kColl id="selfDefOper">
        <!-- Operation registry: XML file path → operation name -->
        <operDef id="Xml Definition/Channel/{CHANNEL}/selfDefOper/GetClientLinks.xml"
                 value="GetClientLinksOp"/>
        <!-- ... one entry per operation ... -->
      </kColl>

      <kColl id="operations">
        <!-- Usually empty; operations are in selfDefOper -->
      </kColl>

    </kColl>

    <kColl id="tags">
      <kColl id="data">        <!-- Data tag → class mappings -->
      </kColl>
      <kColl id="formats">     <!-- Format AND decorator tag → class mappings -->
        <!-- Decorator subsection -->
        <field id="nilDecorator" value="com.ibm.il.dse.cc.decorator.NilDecorator"/>
        <field id="RemoveLeadingZerosDecorator"
               value="com.ibm.il.dse.cc.decorator.RemoveLeadingZerosDecorator"/>
        <!-- ... more decorators ... -->
        <!-- Format subsection -->
        <field id="CCString"   value="com.ibm.il.dse.cc.format.CCString"/>
        <field id="CCDate"     value="com.ibm.il.dse.cc.format.CCDate"/>
        <field id="CCXML"      value="com.ibm.il.dse.cc.format.CCXML"/>
        <field id="CCIColl"    value="com.ibm.il.dse.cc.format.CCIColl"/>
        <!-- ... more formats ... -->
      </kColl>
      <kColl id="contexts">    <!-- Always empty — contexts resolved differently -->
      </kColl>
      <kColl id="services">    <!-- Backend service connectors -->
        <field id="HTTPService" value="com.ibm.il.dse.cc.service.communication.http.HTTPService"/>
      </kColl>
      <kColl id="operations">  <!-- The CCDSEServerOperation base class -->
        <field id="CCDSEServerOperation"
               value="com.ibm.il.dse.cc.cut.CCDSEServerOperation"
               description="compound"/>
      </kColl>
      <kColl id="opSteps">     <!-- opStep tag → class mappings -->
        <field id="GetClientLinksSP"
               value="com.ibm.il.dse.operations.internet.db.GetClientLinksSP"/>
      </kColl>
      <kColl id="processors">  <!-- Processor definitions -->
      </kColl>
      <kColl id="types">       <!-- Type definitions -->
      </kColl>
    </kColl>

  </kColl>
</dse.ini>
```

### Import Chain

A channel's dse.ini may import other dse.ini configurations:

```xml
<kColl id="import">
  <field id="sme"/>
</kColl>
```

This means: merge the `sme` channel's dse.ini into this channel's configuration. Imports are resolved recursively. Channel-specific mappings override imported mappings for the same tag name.

**The `WSBCC_XML` channel's dse.ini is the shared base** — it defines all built-in format and decorator tag mappings. All other channels import from it directly or indirectly. It is the authoritative source for tags like `CCString`, `CCXML`, `CCIColl`, `NumberFormat`, `nilDecorator`, `CCPadding`, etc.

### Tag Resolution

When the runtime encounters a tag name in XML:
1. Look up the tag name in the merged dse.ini `tags` section for this channel
2. The `value` attribute gives the fully qualified Java class name (FQCN)
3. The `description="compound"` flag marks container tags that recursively process child tags
4. If an opStep has an `implClass` attribute in the XML, that overrides the dse.ini lookup

### selfDefOper — Operation Registry

The `selfDefOper` section is the complete operation registry for the channel:

```xml
<operDef id="Xml Definition/Channel/INTERNET/selfDefOper/GetClientLinks.xml"
         value="GetClientLinksOp"/>
```

- `id` = relative path to the operation's XML file
- `value` = the operation name (matches the `CCDSEServerOperation id` attribute in the XML)

**Every operation in the system appears exactly once in its channel's selfDefOper.** This is the authoritative inventory of operations for that channel.

---

## 4. Runtime Execution Model

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

---

## 5. Context

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

---

## 6. Formats and the Format/Unformat Process

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

---

## 7. Decorators

### What a Decorator Is

A decorator is a value transformer chained after a formatter tag. It operates on the string result of the formatter, not on the context directly.

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
| `nilDecorator` | `...decorator.NilDecorator` | Sets `xsi:nil="true"` when value is null/empty |
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

---

## 8. opSteps

### What an opStep Is

An opStep is one step in an operation's execution chain. Each opStep maps to a Java class that performs a specific, bounded piece of business logic — a database call, a backend service call, an error code mapping, a data transformation, a validation check.

### opStep Tag Structure

```xml
<opStep id="GetClientLinks"
        implClass="com.ibm.il.dse.operations.internet.db.GetClientLinksSP"
        on0Do="end"
        on4Do="ErrorDataNotFound"
        on5Do="ErrorInvalidLinks"
        onOtherDo="OperationFailed"
        onlyFor="internet"
        SomeCustomParam="someValue"/>
```

### Reserved Attributes

| Attribute | Description |
|---|---|
| `id` | Unique step name within the operation |
| `implClass` | FQCN of the Java class implementing this step. Overrides dse.ini lookup. |
| `on{N}Do` | Where to go when execute() returns integer N. Can be a step id, "next", or "end" |
| `onOtherDo` | Default routing when no `on{N}Do` matches the return code |
| `onOtherDoDefault` | Final fallback routing (with runtime warning) |
| `onTimeoutDo` | Where to go when execute() returns RC_TIMEOUT |
| `on{N}Return` | When RC=N, switch the error reply format body before routing |
| `onlyFor` | Comma-separated channel names this step runs on. Absent = runs on all channels. |

### Custom Attributes

Any attribute beyond the reserved list is a custom parameter. It is passed to the implClass via a setter method named `set{AttributeName}`:

```xml
<opStep id="MapError"
        implClass="operations.MapErrorByValueAlways"
        ErrorCategory="10"
        ErrorNumber="0"
        onOtherDo="OperationFailed"/>
```

The implClass must implement:
```java
public void setErrorCategory(String value);
public void setErrorNumber(String value);
```

### opStep implClass Contract

Every opStep implClass implements `OperationStepInterface` (directly or via `CCOperationStep`):

```java
public interface OperationStepInterface {
    int execute() throws Exception;
    void setParams(KeyedCollection kc);
    void setOperation(DSEServerOperation op);
    Context getContext();
    String getName();
}
```

The implClass has access to:
- **Context**: via `getContext()` — can read and write any field in the context chain
- **Operation**: via `getOperation()` — provides access to operation-level data
- **Params (KeyedCollection)**: all opStep XML attributes are available via `kc`

### Return Code Routing

The integer returned by `execute()` drives the opStep chain:
- `0` conventionally means success but any integer is valid
- The routing attributes (`on{N}Do`, `onOtherDo`) map return codes to the next step name
- The special step name `"end"` terminates the chain normally
- The special step name `"next"` advances to the immediately following step

---

## 9. CCDSEServerOperation

### What It Is

`CCDSEServerOperation` (package: `com.ibm.il.dse.cc.cut`) is the base class for all WSBCC operations. It extends `AbstractDSEServerOperationIDB`. Every operation XML file's root tag instantiates this class.

### Initialization from XML

When the runtime loads an operation XML file, `initializeFrom(Tag tag)` is called:

1. Reads `id` attribute → sets operation name
2. Reads operation-level attributes: `operationFields`, `hostKey`, `writeToOfecStat`, `writeToLog`, `isSelectiveJournalising`
3. Iterates child tags:
   - `context` sub-tag → instantiates the context via `Context.getExternalizer().convertTagToObject()`
   - `refFormat` sub-tag → loads format via `FormatElement.getExternalizer().convertTagToObject()`, stores in `getFormats()` hashtable
   - `refOpSteps` sub-tag → loads an opStep group
   - `iniValue` sub-tag → loads initial key-value pairs into the context
   - Any other tag → treated as an opStep, initialized via `CCOperationStep.initializeFrom()`
4. Reads all XML attributes and sets them on the operation object

### Operation Attributes

| Attribute | Description |
|---|---|
| `id` | Operation name. Must match the `value` in selfDefOper dse.ini entry. |
| `operationContext` | ID of the context definition this operation uses |
| `operationFields` | Comma-separated `key=value` pairs pre-loaded into context at execute() start |
| `hostKey` | 4-digit identifier for mainframe transaction tracking |
| `writeToOfecStat` | Whether to write to OfecStat logging |
| `writeToLog` | Whether to write to standard log |
| `isSelectiveJournalising` | Controls selective journaling behavior |

### Format Lookup

After `execute()`, the channel handler calls format on the reply format. The operation holds all formats in its `getFormats()` hashtable, keyed by the `name` attribute of `refFormat`:

```java
// Conventionally named formats:
FormatElement requestFmt = (FormatElement) getFormats().get("csRequestFormat");
FormatElement replyFmt   = (FormatElement) getFormats().get("csReplyFormat");
FormatElement errorFmt   = (FormatElement) getFormats().get("csErrorReplyFormat");
```

When an opStep signals an error body change (`on{N}Return`), the operation substitutes `csErrorReplyFormat` for `csReplyFormat` before format() is called.

---

## 10. XML Operation File Structure

### Single-File Structure

An operation may define all its components in one file:

```xml
<?xml version="1.0" encoding="ISO-8859-1"?>
<XML>
    <CCDSEServerOperation id="OperationName" operationContext="OperationCtxt">
        <!-- opSteps -->
        <opStep id="Step1" implClass="..." on0Do="end" onOtherDo="ErrorStep"/>
        <opStep id="ErrorStep" implClass="..." onOtherDo="end"/>
        <!-- format references -->
        <refFormat name="csRequestFormat"  refid="OperationRQFmt"/>
        <refFormat name="csReplyFormat"    refid="OperationRSFmt"/>
    </CCDSEServerOperation>

    <fmtDef id="OperationRQFmt">
        <CCXML dataName="OperationRequest">
            <CCString dataName="Field1"/>
        </CCXML>
    </fmtDef>

    <fmtDef id="OperationRSFmt">
        <CCXML dataName="OperationResponse">
            <CCString dataName="Result"/>
        </CCXML>
    </fmtDef>

    <context id="OperationCtxt" parent="nil" type="op"/>
</XML>
```

### Split-File Structure

Large operations may reference formats and contexts defined in `dseformat.xml` or `dsecontext.xml` using `refFormat`. The format can live anywhere as long as its file is loaded via `defaultFile` in dse.ini.

### File Naming Convention

Operation files in `selfDefOper/` are typically named after the operation: `GetClientLinks.xml`. The `selfDefOper` dse.ini entry maps the file path to the operation name.

---

## 11. Tag Reference

### Format Tags (Formatters)

| Tag | Class | Description |
|---|---|---|
| `CCXML` | `...format.CCXML` | XML element container. Groups child fields. `transparent=true` omits wrapper element from wire format. |
| `CCString` | `...format.CCString` | String field. Reads/writes a string value between XML element and context. |
| `CCDate` | `...format.CCDate` | Date field with pattern formatting. |
| `CCTime` | `...format.CCTime` | Time field. |
| `CCBoolean` | `...format.CCBoolean` | Boolean field. |
| `NumberFormat` | `...format.NumberFormat` | Numeric field with decimal/thousands separator control. |
| `CCIColl` | `...format.CCIColl` | Index-based collection. Iterates a list stored in context and formats/unformats each element. |
| `CCTableFormat` | `...format.CCTableFormat` | Database lookup formatter. Queries DB during format to populate field from a table. |
| `CCDate` | `...format.CCDate` | Date with configurable pattern, separator, year digit options. |
| `CCConstant` | `...format.CCConstant` | Writes a constant value to context/XML regardless of input. |
| `CCRecord` | `...format.CCRecord` | Record structure formatter. |
| `CCLength` | `...format.CCLength` | String with length constraint. |
| `CCEnumFormat` | `...format.CCEnumFormat` | Enumeration mapping formatter. |
| `CCEnum` | `...format.CCEnum` | Enum value formatter. |
| `CCConditionalString` | `...format.CCConditionalString` | Conditional string — value depends on a context condition. |
| `CCConcatObjects` | `...format.CCConcatObjects` | Concatenates multiple context values. |
| `CCReflect` | `...format.CCReflect` | Reflects a value from one context field to another. |
| `CCTagValue` | `...format.CCTagValue` | Writes the tag name as the value. |
| `CCSysTimeDate` | `...format.CCSysTimeDate` | Current system timestamp. |
| `CCTimeDateFormats` | `...format.CCTimeDateFormats` | Combined time/date with multiple format options. |
| `CCHostName` | `...format.CCHostName` | Server hostname. |
| `CCTableFormatMultiLanguage` | `...format.CCTableFormatMultiLanguage` | Multi-language DB lookup. |
| `ValdFIColl` | `...format.ValdFIColl` | Validated index collection. |
| `SumCollFields` | `...format.SumCollFields` | Sums a collection field. |
| `PS10NewXMLFormat` | `...format.PS10NewXMLFormat` | PS10 protocol XML format. |
| `PS10MFormat` | `...format.PS10MFormat` | PS10 M-format. |
| `CCHTTP` | `...format.CCHTTP` | HTTP-specific format handling. |

### Context Tags

| Tag | Description |
|---|---|
| `context` | Defines a context. Attributes: `id`, `parent` ("nil" or parent context id), `type` ("op") |

### Operation Tags

| Tag | Description |
|---|---|
| `CCDSEServerOperation` | Defines a complete operation. See Section 9. |
| `opStep` | Defines one execution step. See Section 8. |
| `refFormat` | References a fmtDef by id with a local role name. |
| `fmtDef` | Defines a format structure inline or in a shared file. |
| `refOpSteps` | References a group of opSteps defined elsewhere. |
| `iniValue` | Pre-loads key-value pairs into the context at operation start. |

---

## 12. Complete Operation Example

```xml
<?xml version="1.0" encoding="ISO-8859-1"?>
<XML>

    <!-- ================================================ -->
    <!-- Operation Definition                              -->
    <!-- ================================================ -->
    <CCDSEServerOperation id="GetClientLinksOp"
                          operationContext="GetClientLinksCtxt"
                          hostKey="GCLN">

        <!-- Step 1: fetch links from DB -->
        <opStep id="GetClientLinks"
                implClass="com.ibm.il.dse.operations.internet.db.GetClientLinksSP"
                on0Do="end"
                on4Do="ErrorDataNotFound"
                on8Do="ErrorTechnical"
                onOtherDo="ErrorTechnical"/>

        <!-- Step 2a: business error — data not found -->
        <opStep id="ErrorDataNotFound"
                implClass="operations.MapErrorByValueAlways"
                ErrorCategory="10"
                ErrorNumber="0"
                on0Return="ErrorBody"
                onOtherDo="end"/>

        <!-- Step 2b: technical error -->
        <opStep id="ErrorTechnical"
                implClass="operations.MapErrorByValueAlways"
                ErrorCategory="99"
                ErrorNumber="0"
                on0Return="ErrorBody"
                onOtherDo="end"/>

        <!-- Format references -->
        <refFormat name="csRequestFormat"     refid="GetClientLinksRQFmt"/>
        <refFormat name="csReplyFormat"       refid="GetClientLinksRSFmt"/>
        <refFormat name="csErrorReplyFormat"  refid="StandardErrorRSFmt"/>

    </CCDSEServerOperation>

    <!-- ================================================ -->
    <!-- Request Format                                    -->
    <!-- ================================================ -->
    <fmtDef id="GetClientLinksRQFmt">
        <CCXML dataName="GetClientLinks">
            <CCString dataName="ClientId"/>
            <nilDecorator/>
            <CCString dataName="BankId"/>
        </CCXML>
    </fmtDef>

    <!-- ================================================ -->
    <!-- Response Format                                   -->
    <!-- ================================================ -->
    <fmtDef id="GetClientLinksRSFmt">
        <CCXML dataName="GetClientLinksResponse" transparent="true">
            <CCString dataName="ClientId"/>
            <CCIColl dataName="Links" times="*">
                <CCXML dataName="Link">
                    <CCString dataName="LinkId"/>
                    <CCTableFormat dataName="LinkDescription"
                                   fromTable="LINK_TYPES"
                                   fromColumn="DESCRIPTION"
                                   keyValue="LinkId"/>
                    <nilDecorator/>
                    <CCDate dataName="LinkDate"
                            pattern="yyyyMMdd"
                            useSep="no"
                            fourDigYear="yes"/>
                </CCXML>
            </CCIColl>
        </CCXML>
    </fmtDef>

    <!-- ================================================ -->
    <!-- Context Definition                                -->
    <!-- ================================================ -->
    <context id="GetClientLinksCtxt" parent="nil" type="op"/>

</XML>
```

### Execution Walkthrough

1. **Channel handler** receives request XML:
   ```xml
   <GetClientLinks>
     <ClientId>001234567</ClientId>
     <BankId>01</BankId>
   </GetClientLinks>
   ```

2. **Unformat** (`csRequestFormat`):
   - `CCXML` tag opens the `<GetClientLinks>` element
   - `CCString[ClientId]` reads `"001234567"` → writes `context["ClientId"] = "001234567"`
   - `nilDecorator` (after CCString[ClientId]) checks if value was null → if so sets `xsi:nil`
   - `CCString[BankId]` reads `"01"` → writes `context["BankId"] = "01"`

3. **execute()** runs the opStep chain:
   - `GetClientLinks` runs `GetClientLinksSP.execute()`:
     - Reads `ClientId` and `BankId` from context
     - Calls stored procedure `CLIENT_LINKS_GET`
     - Writes results to context: `context["Links"] = [list of link objects]`
     - Returns `0` (success) or `4` (not found) or `8` (technical error)
   - RC=0 → route to `"end"` → chain terminates
   - RC=4 → route to `ErrorDataNotFound` → `MapErrorByValueAlways` writes error codes to context, `on0Return="ErrorBody"` signals error body switch → chain terminates

4. **Format** (either `csReplyFormat` or `csErrorReplyFormat`):
   - Success: `CCXML` transparent → no wrapper element emitted
   - `CCString[ClientId]` reads `context["ClientId"]` → writes `<ClientId>001234567</ClientId>`
   - `CCIColl[Links]` iterates `context["Links"]`:
     - For each link: `CCString[LinkId]`, `CCTableFormat[LinkDescription]` (DB lookup), `CCDate[LinkDate]`
   - Error: `StandardErrorRSFmt` serializes error category/number from context

---

## 13. Conversion Guide — WSBCC to Native Java

This section is specifically for LLMs and developers performing the migration from WSBCC XML to native code. It explains the conversion rules for each WSBCC concept.

### Core Conversion Principle

**Do not reimplement the WSBCC framework in the generated code.**

The generated microservice should be the result of evaluating the WSBCC configuration — not a reimplementation of the configuration engine. The XML is a declarative program; generate the equivalent imperative code.

Wrong approach:
```java
// BAD: reimplements framework machinery
FormatEngine.unformat(requestXml, csRequestFormat, context);
opStepChain.execute(context);
FormatEngine.format(context, csReplyFormat);
```

Correct approach:
```java
// GOOD: direct, evaluated result
String clientId = XmlUtil.getText(requestXml, "GetClientLinks/ClientId");
String bankId   = XmlUtil.getText(requestXml, "GetClientLinks/BankId");
List<Link> links = db.getClientLinks(clientId, bankId);
return buildLinksResponse(clientId, links);
```

### Conversion Rules by Concept

**Channel filtering (onlyFor):**
When converting for channel X, omit all opSteps whose `onlyFor` attribute does not include X. The generated class only contains the steps that actually run for that channel.

**Context:**
Context fields become local variables or fields on a simple operation-scoped data class. No dynamic hashtable. Use typed fields.
```java
// context["ClientId"] = "001234567"  →  String clientId = "001234567";
```

**Format/unformat:**
Replace with direct XML parsing (JAXB or DOM) for request, and direct XML building for response. The format tree defines the XML structure — generate JAXB annotated classes matching that structure.

**Decorator chain:**
Evaluate what the decorator chain does and write equivalent inline code:
```java
// CCString + RemoveLeadingZerosDecorator + CCPadding(9, '0')
// In unformat: strip leading zeros from parsed value
String accountId = parseString(xml, "AccountId").replaceFirst("^0+", "");
// In format: pad to 9 chars with leading zeros
String xmlValue = String.format("%09d", Long.parseLong(accountId));
```

**opStep implClass:**
If the implClass contains only IBM framework plumbing around business logic, extract the business logic and write it directly. If the implClass is already business logic (DB call, validation, calculation), keep the logic and remove IBM infrastructure.

**RC routing:**
The opStep chain routing logic (`on{N}Do`, `onOtherDo`, `onTimeoutDo`, `on{N}Return`) is defined in the operation XML — not in any Java class. When converting, read the operation XML's opStep routing attributes to determine the complete flow, then generate the equivalent imperative branching. The XML is the source of truth for flow control; the implClass only produces a return code and does not know what happens next.

```java
int rc = getClientLinksSP(clientId, bankId, context);
if (rc == 0) {
    return buildSuccessResponse(context);
} else if (rc == 4) {
    return buildErrorResponse("10", "0");
} else {
    return buildTechnicalError();
}
```

**CCTableFormat DB lookup:**
`CCTableFormat` is a DB lookup that was incorrectly placed inside a format definition in WSBCC — mixing serialization concerns with business logic. Do not carry this mistake into the converted code. JAXB classes are pure data carriers with no logic; they never perform DB calls.

The correct conversion is to move the lookup to the service/business logic layer, where it belongs. Execute the DB query during the opStep phase and store the result in the response object before serialization begins. By the time the JAXB serializer runs, every field — including those that were `CCTableFormat` in the original XML — must already be populated.

```java
// In the service layer (opStep equivalent), not in the serializer:
String description = linkTypeRepository.findDescriptionByKey(linkId);
linkDto.setDescription(description);

// The JAXB class is a plain DTO — no logic, no DB calls:
@XmlElement(name = "LinkDescription")
public String getDescription() { return description; }
```

When you encounter a `CCTableFormat` in a fmtDef, treat it as a signal that a DB lookup is missing from the opStep layer. Add it there.

**Shared components:**
Any implClass used by more than one operation goes into `common-lib` as a shared utility class. The generated service imports it rather than duplicating the logic.

**Naming:**
For operations that exist in multiple channels, append the channel name:
```
GetClientLinksOp in INTERNET channel → GetClientLinksService (internet package)
GetClientLinksOp in IVR channel     → GetClientLinksService (ivr package)
```

---

## 14. Best Practices

### For WSBCC Developers

1. **Format reuse**: Define shared formats in `dseformat.xml` and reference via `refFormat`. Never duplicate format structures — a shared format changed in one place updates all operations.
2. **Context sizing**: Define context fields only for the operation's actual data needs. Do not use context as a global scratchpad.
3. **Return codes**: Document all return codes in the implClass Javadoc. Ensure every possible RC is handled by `on{N}Do` or `onOtherDo`.
4. **onlyFor**: Use sparingly. Each `onlyFor` opStep is invisible to other channels — prefer separate operations over invisible conditional logic.
5. **Decorator order**: The order of decorator tags is the execution order during format. Reverse order runs during unformat. Document the intended transformation chain with a comment.
6. **Error body switching**: When an opStep uses `on{N}Return`, ensure `csErrorReplyFormat` is defined on the operation. Missing error format causes a silent null response.

### For Conversion

1. **Read the implClass source before converting** — the XML tag tells you what class to call; the Java source tells you what it actually does.
2. **Evaluate, don't translate** — generate code that does what the WSBCC XML does, not code that looks like the XML.
3. **Channel first** — always establish which channel before converting an operation. The channel determines which opSteps run.
4. **Verify decorator chains** — decorator behavior in format vs unformat direction is frequently asymmetric. Read both `addDecoration` and `removeDecoration` before generating equivalent code.
5. **CCTableFormat is a DB call** — it is not just a format tag. The generated code needs a DB query at the point where this tag would have executed.


---

> **Code structure and separation of concerns rules for each target language are defined in the generation skill files.**
> See `skills/java_generation_skills/spring_boot_structure.md` for Java/Spring Boot,
> `skills/nodejs_generation_skills/express_structure.md` for Node.js/Express, and
> `skills/python_generation_skills/fastapi_structure.md` for Python/FastAPI.
> Language-agnostic conversion rules (evaluate don't translate, channel-first, shared components, etc.)
> are in `skills/conversion_rules_skill.md`.

---

## Appendix A: Format Tag Quick Reference

### CCString Attributes
| Attribute | Description |
|---|---|
| `dataName` | XML element name and context field name |

### CCDate Attributes
| Attribute | Description |
|---|---|
| `dataName` | XML element name |
| `pattern` | Date format pattern (e.g. `yyyyMMdd`) |
| `useSep` | Use separators (`yes`/`no`) |
| `fourDigYear` | Use 4-digit year (`yes`/`no`) |
| `ordering` | Component order (`ymd`, `dmy`, `mdy`) |
| `usePattern` | Apply the pattern (`yes`/`no`) |
| `onFailed` | Behavior on parse failure (`current` = use current date) |

### CCXML Attributes
| Attribute | Description |
|---|---|
| `dataName` | XML element name |
| `transparent` | When `true`: element wrapper is not emitted; children appear at parent level |
| `unnamed` | Controls whether `dataName` appears as the element name |

### CCIColl Attributes
| Attribute | Description |
|---|---|
| `dataName` | Collection element name |
| `times` | Max iterations, or `*` for unlimited |
| `transparentSource` | Whether source is transparent |
| `append` | Append to existing collection |

### NumberFormat Attributes
| Attribute | Description |
|---|---|
| `dataName` | XML element name |
| `showThousandsSep` | Include thousands separator (`yes`/`no`) |
| `showDecimalsSep` | Include decimal separator (`yes`/`no`) |

### CCTableFormat Attributes
| Attribute | Description |
|---|---|
| `dataName` | XML element name |
| `fromTable` | Database table to query |
| `fromColumn` | Column to retrieve |
| `keyValue` | Context field name whose value is the lookup key |

---

## Appendix B: Channel List

| Workspace | Channel Name | Description |
|---|---|---|
| `WSBCC_ARNAV` | ARNAV | ARNAV channel |
| `WSBCC_BANKADMIN` | BANKADMIN | Bank administration |
| `WSBCC_G2` | G2 | G2 channel |
| `WSBCC_GVP` | GVP | GVP channel |
| `WSBCC_INTERNET` | INTERNET | Internet banking |
| `WSBCC_IVR` | IVR | Phone/IVR banking |
| `WSBCC_KIOSK` | KIOSK | Kiosk banking |
| `WSBCC_MKT` | MKT | Marketing |
| `WSBCC_ONLINEGOV` | ONLINEGOV | Online government services |
| `WSBCC_SME` | SME | Small/medium enterprise banking |
| `WSBCC_TRANSFERS` | TRANSFERS | Transfers |
| `WSBCC_WEB` | WEB | Web channel |
| `WSBCC_WS` | WS | Web services |
| `WSBCC_XML` | XML | Common shared definitions (imported by all channels) |

---

## Version History

| Version | Date | Changes |
|---|---|---|
| 1.0 | 2026-01-27 | Initial release |
| 2.0 | 2026-05-25 | Complete rewrite. Added: runtime execution model, CCDSEServerOperation internals, dse.ini complete structure, channel/workspace inventory, decorator contracts and chain rules, context inheritance, format/unformat direction, CCTableFormat DB lookup behavior, onlyFor channel filtering, RC routing full priority chain, conversion guide for LLM and human developers. |
