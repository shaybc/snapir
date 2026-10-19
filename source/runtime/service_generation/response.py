"""Parse generated wrapper JSON and retain actionable correction evidence."""

import json
import re

from runtime.behavior_conversion.response_json import clean_structural_escapes
from runtime.managed_conversion_response import _remove_response_fence

RESPONSE_VERSION = 'service-response-xml-media-validation-v2'
RESPONSE_INSTRUCTION = (
    'Return one valid JSON object with files and dependencies, including every correction response. '
    'Quote every property name; separate properties with commas, and escape Java source only inside '
    'its JSON string. Never include prose, comments or Markdown in the JSON. Validate the entire response '
    'before returning it. When response_correction is supplied, fix its exact syntax error and return the '
    'complete object using previous_generation_response; do not return a patch. '
    'Feedback fields ending in _ref refer to the retained top-level field of that name in this same request. '
    'required_classes describes APIs provided by a dependency or its resolved transitives. Classes supplied '
    'by the configured JDK need no Maven owner; do not add or change a dependency merely to supply them.')


class ServiceResponseError(ValueError):
    """Keep the raw rejected response and precise parser location for the next attempt."""

    def __init__(self, response, error, text):
        super().__init__(f'Generated response contains invalid JSON: {error.msg} at line {error.lineno}, column {error.colno}')
        paths = list(re.finditer(r'"(src/[^"\r\n]+)"\s*:', text[:error.pos]))
        self.response = response
        self.feedback = dict(category='json_parse', message=error.msg, line=error.lineno,
            column=error.colno, offset=error.pos, excerpt=text[max(0, error.pos - 100):error.pos + 100],
            source_path=paths[-1][1] if paths else None,
            correction='Correct the JSON syntax at this location. Return the complete files/dependencies object with quoted keys, commas and properly escaped source strings. Preserve approved sources and accepted tests; no prose, comments, fences or partial patch.')


def parse_service_response(response):
    """Apply the existing fence/structural cleaner, then reject malformed JSON precisely."""
    text = clean_structural_escapes(_remove_response_fence(response))
    try:
        result = json.loads(text)
    except json.JSONDecodeError as exc:
        raise ServiceResponseError(response, exc, text) from exc
    if not isinstance(result, dict) or not isinstance(result.get('files'), dict) or not isinstance(result.get('dependencies'), list):
        raise ValueError('Service response must be one JSON object containing a files object and dependencies array')
    return result


def attach_response_correction(payload, cached):
    """Supply rejected JSON once, keeping feedback references within the same request."""
    if not cached.get('response_correction'):
        return
    payload['response_correction'] = cached['response_correction']
    payload['previous_generation_response'] = cached['previous_generation_response']
    feedback = dict(payload.get('validation_feedback', {}))
    feedback.pop('previous_generation_response', None)
    feedback.pop('response_correction', None)
    feedback['previous_generation_response_ref'] = 'previous_generation_response'
    feedback['response_correction_ref'] = 'response_correction'
    payload['validation_feedback'] = feedback
