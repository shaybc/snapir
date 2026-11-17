# Native format API — version 1

This directory is the common Java source contract for the separate format-library tool.
Copy the complete `src/main/java` tree into each prepared conversion folder. Keep its package,
method signatures and version consistent across approved components.

- `NativeFormat` defines only `format` and `unformat`. Both formats and decorators implement it.
- `XmlElement` carries namespace-qualified XML names, namespace declarations, attributes and
  ordered text/child content. It has no parsing or serialization engine.
- `FormatContext` carries caller-owned mutable runtime fields. It has no Composer runtime logic.

The API uses JDK types only and requires Java 17 or later. Implementations may use Jackson XML
behind this contract. No Jackson adapter, library dependency or formatter implementation is
included at this stage. Do not use default Jackson record serialization as an XML mapping:
the XML must represent the names, attributes and content carried by `XmlElement`, not its Java
record field names. An adapter must preserve those documented semantics.

Supply component-specific settings through constructors. Supply a decorator's wrapped
`NativeFormat` through its constructor, and supply a wrapper's configured native children
through its constructor. Their precise constructor arguments belong to the generated component
contract. Do not add generic chain execution methods to the common interface. Preserve delegation,
conditions, before/after hooks and call order from the source; unformat is not assumed to invert format.

Formatting receives an explicit native value. Context is available for additional source-defined
reads and writes; a null value does not automatically mean “look it up in context.” Unformat returns
the parsed native value and may also update context where the original implementation does so.
Callers use map key presence to distinguish missing fields from explicit nulls. Do not rebuild
Composer Context, DataElement, Tag or its reflective framework under different names.

The context is shared within an invocation; callers must provide appropriate isolation for concurrent
invocations. XML structure is immutable. Text is unescaped data, not raw XML fragments. This API
does not promise preservation of lexical XML choices such as quote style or self-closing syntax.

Generated exported components accept definition attributes through a Map<String,String> constructor
argument and implement their own initialization, defaults and validation. This does not add an
attribute-to-settings metadata mechanism or change the shared interface signatures.

The API is not connected to the migration converter. The separate parent tool prepares these files
and generates reviewed candidates; this API directory contains no parser, model client or execution
engine. See ../README.md for the standalone CLI workflow.
