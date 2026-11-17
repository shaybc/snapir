"""Recognize whole-response delivery errors without validating generated JSON schemas."""
import json
import re


class UpstreamResponseError(RuntimeError):
    """An endpoint returned error content instead of usable model output."""


def reject_delivery_error(response):
    """Raise a retryable delivery error for recognizable upstream/HTML error bodies.

    Valid JSON containing source code, HTML strings, or business error fields is
    left to the caller's normal schema validation. No response text is logged here.
    """
    body = response.lstrip('\ufeff \t\r\n')
    if re.match(r'(?is)^(?:<!--.*?-->\s*)*(?:<!doctype\s+html\b|<html\b|<head\b|<body\b)', body):
        raise UpstreamResponseError('No usable model message received: endpoint returned an HTML page; possible upstream or bridge delivery failure')
    if re.match(r'(?is)^(?:Failed to fetch response\b|upstream (?:connect error|request timeout)\b|'
                r'(?:(?:HTTP(?:/\d(?:\.\d)?)?\s+)?(?:429|500|502|503|504)\s+)?'
                r'(?:Bad Gateway|Gateway Time[- ]?out|Service Unavailable|Internal Server Error|Too Many Requests)\b)', body):
        raise UpstreamResponseError('No usable model message received: endpoint returned upstream error content; possible provider or bridge delivery failure')
    if not body.startswith('{'): return
    try:
        value = json.loads(body)
    except ValueError:
        return  # Malformed generated JSON belongs to the semantic correction loop.
    if not isinstance(value, dict) or set(value) - {'error', 'status', 'status_code', 'code', 'request_id', 'id'}:
        return
    error = value.get('error')
    if not isinstance(error, dict): return
    code = error.get('code', value.get('status_code', value.get('code', value.get('status'))))
    kind = error.get('type')
    if str(code) in {'429', '500', '502', '503', '504'} or isinstance(kind, str) and kind in {
            'server_error', 'api_error', 'rate_limit_error', 'overloaded_error', 'unavailable_error'}:
        raise UpstreamResponseError('No usable model message received: endpoint returned an upstream error envelope; possible provider or bridge delivery failure')
