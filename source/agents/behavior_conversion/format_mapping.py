"""Generate Jackson models and direction-specific native format transformations."""

from agents.behavior_conversion.native_instructions import native_instructions

XML_NULL_MAPPING_GUIDANCE = """XML null mapping and correction checks:
Preserve absent, empty and nil values according to the supplied format configuration and
supporting behavior evidence. Apply xsi:nil to the specific element whose value is null,
not its parent, siblings or document root. A nil root is valid only when the entire root
value is evidenced to be null; a nullable child must not make a populated response nil.
Model nullable child elements at their own XML scope, using an element wrapper or explicit
element-level serialization when needed. Declare the XML Schema instance namespace correctly.
On input, interpret an element's nil marker at that element only; preserve its siblings.
Do not use a root-level nil attribute as a global flag for a nullable child.
Test the actual serialized XML structure and attribute placement independently of round-trips:
a null child leaves the populated root and siblings intact, and deserialization preserves
their values. Test evidenced non-null, missing, empty and nil cases without inventing rules.
When correcting a parsing/test failure, trace the serialized element and its annotations
back to the evidenced field. Fix incorrect nil placement or mapping rather than merely
adding a null guard, changing the exception, discarding data or weakening the test.
"""

INSTRUCTION = native_instructions("format") + """Return unit_contract with this unit_id, exact fully qualified public APIs matching the returned files, requirements and evidence_ids. Include input_type, output_type and wire_type where applicable. Generate typed data classes needed by this unit in the same bundle. dependency_units may name only supplied accepted units. Use the assigned native_package.
Implement the complete configured format unit and native APIs you declare in this response.
For request_unformat produce Jackson XML wire models plus explicit post-parsing conversion
methods returning a typed business input object. Generate both the Jackson-annotated wire
model and the business input class in this bundle unless an accepted dependency provides them.
The request flow is XML -> Jackson wire model -> explicit mapper -> typed business input.
For example, TransferRequest toBusinessInput(TransferRequestXml wire) returns populated typed
fields after evidenced conversions and decorator removal; it does not mutate a Context.
Use XmlMapper or the Spring Jackson XML converter for structural XML parsing, not Composer
formatters. The legacy sources explain behavior; their runtime classes are not reusable APIs.
Do not import IBM classes, create a Context class, rename Context into a generic data holder,
or use Map<String, Object> or string-key get/set access as a replacement context engine.
No generated main or test method may accept a Context parameter. Use explicit typed fields,
arguments and return values. Tests must assert the returned business object's field values.
For response_format, map a typed business result into a Jackson-annotated response wire model,
then serialize that model to XML. Apply evidenced formatter conversions and decorations in
that mapper, without context lookup or a recreated formatter/decorator framework.
Implement decorator behavior as plain mapper logic: padding/stripping is string logic,
nil handling maps the evidenced XML attribute/value to a typed nullable field, and other
transformations are explicit Java expressions or small mapper methods. Preserve the
evidenced order: remove decorations in reverse order for requests, apply decorations in
forward order for responses. Do not generate Tag, FormatDecoratorHolder, CCPadding,
NilDecorator or copied Composer decorator classes, even under the native package.
Do not recreate initializeFrom(Tag), addDecoration/removeDecoration or a decorator chain
engine. Read configuration from the supplied XML during conversion and encode its values
in the mapper. Use Jackson annotations for XML attributes and ordinary Java transformations
for values; do not merely rename or relocate legacy classes. Add tests for the confirmed
padding, nil and transformation behavior directly on the mapper and typed result.
Preserve roots, children, attributes and nesting;
implement conversions and decorator order using source, configured attributes and documented
semantics. Do not recreate a Composer interpreter or individual formatter hierarchy.
Do not infer scaling from output decimal precision. Preserve absent/empty/nil distinctions
where evidenced. Reuse accepted dependency APIs; do not redefine them.
Return a bundle matching schema with main Java files and executable test Java files under
src/test/java. coverage maps every supplied requirement ID to returned test file paths.
Test expected XML/value behavior derived from evidence, not only round-trips. Expose uncertain
behavior in unresolved_questions. Dependencies must have verified coordinates and versions.
Address correction_feedback, behavior_review_feedback and final_validation_feedback without changing the agreed APIs. Check the complete JSON for
valid escaping; return no fences, prose or build files.""" + "\n" + XML_NULL_MAPPING_GUIDANCE
