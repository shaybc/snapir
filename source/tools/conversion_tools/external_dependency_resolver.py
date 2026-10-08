"""Match external dependency rules and preserve replacement evidence."""

import constants

from runtime.composer_behavior_context import required_composer_behavior


def external_dependency(name, rules, document, origin, allow_framework=False):
    """Prefer exact classes, then the most specific package boundary."""
    matching = [rule for rule in rules if rule.class_name == name or
                (rule.package_prefix and name.startswith(rule.package_prefix.rstrip(".") + "."))]
    if not matching:
        if allow_framework and any(name.startswith(package.rstrip(".") + ".") for package in constants.COMPOSER_FRAMEWORK_PACKAGES):
            return dict(class_name=name, treatment="replace", maven_coordinates=None,
                        behavior_description="Replace Composer runtime behavior using the embedded component contracts",
                        behavior_evidence=required_composer_behavior(), origin=origin)
        return None
    rule = max(matching, key=lambda item: (item.class_name is not None, len(item.package_prefix or "")))
    if rule.treatment == "replace" and not name.startswith(("com.ibm.dse.", "com.ibm.il.dse.")) and not rule.behavior_description.strip():
        raise ValueError("Third-party replacement requires behavior_description: " + name)
    evidence = required_composer_behavior() if rule.treatment == "replace" else []
    return dict(class_name=name, treatment=rule.treatment, maven_coordinates=rule.maven_coordinates,
                behavior_description=rule.behavior_description, behavior_evidence=evidence, origin=origin)
