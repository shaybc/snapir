"""Reject vendor framework references that a component must replace before compilation."""

import re

from runtime.java_public_type import _code


def validate_composer_replacements(source, replacements):
    """Report retained replacement type names, ignoring comments and string literals."""
    code = _code(source)
    declared = set(re.findall(r"(?:class|interface|enum|record)\s+([\w$]+)", code))
    unresolved = []
    for record in replacements:
        if record.get("treatment") != "replace":
            continue
        name = record["class_name"]
        short = name.rsplit(".", 1)[-1]
        qualified = re.search(r"(?<![\w$])" + re.escape(name) + r"(?![\w$])", code)
        reference = re.search(r"(?<![\w$])" + re.escape(short) + r"(?![\w$])", code)
        if qualified or (reference and short not in declared):
            unresolved.append(name)
    if unresolved:
        raise ValueError("Conversion retains framework types marked for replacement: " + ", ".join(sorted(set(unresolved))) +
                         ". Implement their documented behavior in native Java; do not retain or merely rename unavailable base classes or calls. No compilation was attempted.")
