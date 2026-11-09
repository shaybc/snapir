"""Recognize documented Composer contracts without treating every IBM class as Composer."""

import re
from runtime.composer_behavior_context import required_composer_behavior


def composer_class(name):
    """Identify Composer ownership; other IBM products remain ordinary approved libraries."""
    return name.startswith(('com.ibm.dse.', 'com.ibm.il.dse.', 'com.ibm.wsbcc.'))


def documented_contract(name):
    """Return the documented scope, never invent behavior for an unfamiliar Composer type."""
    if not composer_class(name):
        return []
    simple = name.rsplit('.', 1)[-1]
    sections = required_composer_behavior()
    matches = [item for item in sections if re.search(r'(?<!\w)' + re.escape(simple) + r'(?!\w)', item['content'])]
    # The manual's format/decorator protocols also cover their framework base contracts.
    if not matches and simple in {'AbstractFormatElement', 'FormatElement', 'AbstractDecorator', 'FormatDecoratorHolder'}:
        matches = [item for item in sections if 'Format' in item['heading'] or 'Decorator' in item['heading']]
    return matches
