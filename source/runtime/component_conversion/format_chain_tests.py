"""Keep chain regressions stable while separating test syntax from production repair."""
import re
from tools.validation_tools.java_comments import mask_java_comments

INSTRUCTION='''For configured chains, test the selected direction only, with public top-level JUnit classes.
Derive expected values from the original source/configuration, not from the generated implementation.
Include null, missing, empty and decorator-produced empty values where the source distinguishes them.
Compare XML structurally (element names, namespaces, attributes and text), not empty-tag spelling,
attribute order or prefix spelling. Never change a source-based empty-string expectation to null to
match a codec round-trip. Retained failing regression tests must rerun after production repair.'''


def validate_chain_tests(tests, payload):
    """Reject lexical XML oracles before they can masquerade as business defects."""
    if not payload.get('format_chains'):return
    for file in tests.files:
        code=mask_java_comments(file.content)
        if re.search(r'\bassertEquals\s*\(\s*"\s*<',code) or re.search(r'\.contains\s*\(\s*"\s*<',code):
            raise ValueError('Configured XML tests must compare element/attribute/text structure, not literal XML strings or empty-tag spelling; retain all value and nil-condition assertions')


def assertion_regression(error, payload):
    """Treat executed value disagreements as production repair, never rewritten expectations."""
    details=getattr(error,'test_correction',None)
    if not payload.get('format_chains') or not details:return None
    failures=details.get('diagnostics',[])
    if not failures or any(item.get('category')!='assertion_failure' for item in failures):return None
    return dict(stage='format_chain_regression',errors=['Compiled composition disagrees with its retained source-based regression tests. Repair production against the original evidence; do not weaken these tests.'],test_correction=details)
