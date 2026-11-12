"""Classify saved AI evidence without rewriting code or asserting HTTP success."""
import json
import re


def finding(response=None, error=None, *, completed=False):
    """Return evidence-level outcomes; conversion acceptance is reported separately."""
    has_error = error is not None
    if completed and not has_error:
        return 'saved_validation_passed'
    text = str(error or '')
    body = (response or '').lstrip()
    if re.match(r'(?is)(?:<!doctype\s+html|<html\b|Failed to fetch response\b)', body):
        return 'html_or_upstream_error_content'
    lower = text.lower()
    if 'tokenizer setup' in lower or 'model setup incomplete' in lower:
        return 'not_sent_setup_failure'
    if 'context budget' in lower or 'too_large' in lower:
        return 'not_sent_oversized'
    if 'converter boundary analysis' in lower and ('timeout' in lower or 'timed out' in lower):
        return 'blocked_analysis_timeout'
    if ('no parser-backed entry' in lower or 'entry method' in lower or 'lifecycle could not be resolved' in lower
            or 'requires identified original boundary' in lower):
        return 'blocked_entry_resolution'
    if 'prerequisite' in lower:
        return 'blocked_prerequisite'
    if 'invalid escape' in lower:
        return 'invalid_json_escape'
    if 'invalid json' in lower or 'json_invalid' in lower:
        return 'invalid_json_syntax'
    if response is not None:
        if not body:
            return 'empty_response'
        from runtime.behavior_conversion.response_json import clean_structural_escapes
        from runtime.managed_conversion_response import _remove_response_fence
        try:
            json.loads(clean_structural_escapes(_remove_response_fence(response)))
        except (ValueError, TypeError):
            return 'invalid_json_syntax'
        if has_error:
            if 'validation error' in lower or 'validation errors' in lower:
                return 'schema_validation_failed'
            for marker, result in (('compil', 'compilation_failed'), ('test execution failed', 'tests_failed'),
                                   ('test failure', 'tests_failed'), ('junit', 'tests_failed'),
                                   ('behavior', 'behavior_validation_failed'), ('validation error', 'schema_validation_failed'),
                                   (' api ', 'api_validation_failed')):
                if marker in lower:
                    return result
            return 'candidate_validation_failed'
        return 'saved_validation_passed' if completed else 'json_received_validation_unknown'
    status = re.search(r'\b(?:HTTP(?:\s+status)?|status(?:_code)?\s*[:=]?)\s*(401|403|429)\b', text, re.I)
    if status:
        return {'401': 'authentication_failure', '403': 'access_denied', '429': 'rate_limited'}[status[1]]
    for marker, result in (('authenticationerror', 'authentication_failure'), ('unauthorized', 'authentication_failure'),
                           ('ratelimiterror', 'rate_limited'), ('timeout', 'timeout'),
                           ('timed out', 'timeout'), ('cannot post', 'route_failure'),
                           ('notfounderror', 'route_failure')):
        if marker in lower:
            return result
    return 'failure_without_response' if has_error else 'saved_validation_passed' if completed else 'in_progress_or_unknown'


def error_location(error):
    """Expose a parser location without printing arbitrary source/error payloads."""
    match = re.search(r'line\s+(\d+)\s+column\s+(\d+)', str(error or ''), re.I)
    return dict(line=int(match[1]), column=int(match[2])) if match else None
