"""Reject reflective production APIs; tool-owned harness reflection remains separate."""
import re
from runtime.java_public_type import _code


INSTRUCTION = '''Generated production Java must not use reflection, reflective bean/property access,
dynamic proxies, MethodHandles, class loading or reflective construction, even in unused helpers.
Replace known source reflection targets with direct typed calls. If the source selects targets at
runtime, use an ordinary typed interface and explicit factory/dispatcher driven by evidenced input
or state. Do not invent targets or recreate a generic Composer engine. If the target set cannot be
determined from evidence, report it as unresolved rather than using reflection. This restriction
applies to generated production sources, not the converter's controlled verification harness.
'''


def reject_native_reflection(path, source):
    """Catch reflective API declarations and Class lookups before compilation, including dead helpers.

    Comments/literals are masked. Ordinary typed methods named invoke are allowed; the existing
    resolved-call harness guard remains a second check for indirect/uncontrolled execution.
    """
    if not path.startswith('src/main/java/'):
        return
    code = _code(source)
    forbidden = re.search(r'\b(?:java\s*\.\s*lang\s*\.\s*(?:reflect|invoke)\b|'
                          r'ClassLoader\b|ServiceLoader\s*\.\s*load\s*\(|'
                          r'(?:sun\s*\.\s*misc|jdk\s*\.\s*internal\s*\.\s*misc)\s*\.\s*Unsafe\b|'
                          r'(?:org\s*\.\s*apache\s*\.\s*commons\s*\.\s*beanutils|'
                          r'org\s*\.\s*apache\s*\.\s*commons\s*\.\s*lang3?\s*\.\s*reflect|'
                          r'org\s*\.\s*springframework\s*\.\s*(?:beans\s*\.\s*BeanWrapper|util\s*\.\s*ReflectionUtils)|'
                          r'java\s*\.\s*beans\s*\.\s*Introspector)\b)', code)
    # Class is implicitly imported by Java; no reflection import is needed for these calls.
    variables = re.findall(r'\bClass\s*(?:<[^;=(){}]+>)?\s+([A-Za-z_$][\w$]*)', code)
    variables += re.findall(r'\bvar\s+(\w+)\s*=\s*(?:[\w.]+\s*\.\s*class|(?:[\w.]+\s*\.)?getClass\s*\(\s*\))', code)
    receivers = '|'.join(map(re.escape, ['Class', *variables]))
    lookup = re.search(r'(?:\b(?:' + receivers + r')|\.\s*class|\bgetClass\s*\(\s*\))\s*'
                       r'(?:\.|::)\s*(?:forName|newInstance|getClassLoader|getDeclared\w*|'
                       r'getMethod|getMethods|getField|getFields|getConstructor|getConstructors)\b', code)
    if forbidden or lookup:
        finding = (forbidden or lookup).group()
        raise ValueError('Reflection is forbidden in generated production source ' + path + ': ' + finding +
                         '. Use direct typed calls or an evidence-based typed dispatcher; report unknown targets as unresolved.')
