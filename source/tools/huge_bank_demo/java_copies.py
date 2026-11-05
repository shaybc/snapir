"""Duplicate existing channel-specific Java steps while retaining shared implementations."""

import re


def channel_steps(source):
    """Read channel step sources; common validation/error steps remain shared unchanged."""
    steps = []
    for path in sorted((source / 'composer/Workspace').rglob('*.java')):
        text = path.read_text(encoding='utf-8')
        package = re.search(r'^package\s+([\w.]+)\s*;', text, re.MULTILINE)
        if package and '.operations.' in package[1] and '.operations.common' not in package[1]:
            steps.append((path.relative_to(source), package[1] + '.' + path.stem, text))
    return steps


def copy_step_sources(steps, suffix):
    """Yield renamed existing classes; business statements and external service names stay intact."""
    for relative, name, text in steps:
        simple = name.rsplit('.', 1)[1]
        renamed = re.sub(r'\b' + re.escape(simple) + r'\b', simple + suffix, text)
        yield relative.with_name(relative.stem + suffix + '.java'), renamed.encode('utf-8')
