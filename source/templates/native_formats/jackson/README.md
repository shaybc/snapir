# Verified complete-format example

`FormatExample.java` and `FormatExampleTest.java` form one working reference bundle.
They are verified on Java 25, Jackson XML 2.15.2 and JUnit Jupiter 5.10.0.
The application supplies both files in every complete-format generation and correction
request. Op-steps do not receive this format example.

Use the XML-specific `ToXmlGenerator.Feature.WRITE_XML_DECLARATION` setting,
real Jackson objects, separate parsing/serialization assertions and field-level nil mapping.
Mockito is unnecessary for pure mapping; use the central testing platform only when a
real external collaborator needs mocking.

The example's names, padding width, numeric scaling, date pattern and null rules are
illustrative. Derive migration behavior and expected values from its source/configuration,
including any different absent/empty/nil rules. Preserve the current known dependency
versions and scopes; the example's verification versions do not override the run's inventory.
