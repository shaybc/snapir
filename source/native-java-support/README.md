# Native formatter feasibility prototype

This dependency-free Java prototype demonstrates a shared native implementation
that converted formatters can extend. It uses JDK XML and `java.time` APIs and has
no IBM imports. It is not yet connected to migration scheduling or prompts.

`AbstractFieldFormatter<T>` owns named context access, XML serialization/parsing,
forward decoration during formatting, and reverse decoration during unformatting.
Subclasses implement `formatValue` and `unformatValue`, with optional failure
fallbacks and context-access overrides. `ValueDecorator` transforms strings only.

`TimeFieldFormatter` shows how a CCTime replacement can reuse the base. Its caller
must supply a `DateTimeFormatter` and a `ZoneId`. It formats `LocalTime` or a legacy
`Date`, and parses to `LocalTime`. These are explicit prototype choices, not claims
about IBM TimeFormat defaults. Reuters-specific parsing and timezone/table offsets
require their own documented implementation.

Example construction:

```java
var time = new TimeFieldFormatter("ExecutionTime",
    DateTimeFormatter.ofPattern("HH:mm:ss"), ZoneId.of("Asia/Jerusalem"), List.of());
var context = new HashMap<String, Object>();
context.put("ExecutionTime", LocalTime.of(12, 30));
String xml = time.format(context);
time.unformat(xml, context);
```

The base handles one leaf field. Missing input leaves the context untouched;
multiple matching fields are rejected. Null output produces an empty XML field.
The prototype excludes format trees, namespaces, context hierarchy implementation,
and Composer lifecycle/preprocessing flags. Those contracts must be established
before adopting it as the application support library.

Verified on JDK 21 and 25: time round-trip, forward/reverse decorator order,
legacy Date formatting in the supplied timezone, invalid-time rejection, duplicate
field rejection, and XML escaping/round-trip. Verification used disposable output
folders; the bank demo and migration pipeline remain unchanged.
