"""Check replacement validation before a generated component can reach compilation."""

import pytest

from runtime.composer_replacement_validation import validate_composer_replacements

RULES = [{"class_name": "com.ibm.dse.base.AbstractFormatElement", "treatment": "replace"}]


@pytest.mark.parametrize("source", [
    "class CCXML extends AbstractFormatElement {}",
    "class CCXML extends com.company.generated.AbstractFormatElement {}",
    "class CCXML { void run() { AbstractFormatElement.create(); } }",
])
def test_retained_replacement_references_fail(source):
    with pytest.raises(ValueError, match="No compilation was attempted"):
        validate_composer_replacements(source, RULES)


def test_comments_literals_and_supplied_native_implementation_are_allowed():
    validate_composer_replacements('class CCXML { String s = "AbstractFormatElement"; /* AbstractFormatElement */ }', RULES)
    validate_composer_replacements('class AbstractFormatElement {} class CCXML extends AbstractFormatElement {}', RULES)
    validate_composer_replacements('class CCXML extends AbstractFormatElement {}', [{**RULES[0], "treatment": "retain"}])
