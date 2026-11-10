"""Measure serialized request weight without logging source, prompts or credential values."""
import json
import logging

logger = logging.getLogger(__name__)


def log_request_size(request, encoded, instruction, limit, *, stage):
    """Report the application payload/instruction UTF-8 estimate, not tokens or HTTP envelope bytes.

    KB/MB/GB use decimal units. The character budget remains authoritative; byte
    metrics include JSON escaping and all embedded file/evidence text.
    """
    components = {name: _weight(json.dumps(value, ensure_ascii=False)) for name,value in request.items()}
    total = _weight(encoded + instruction)
    files, blocks, content_bytes = set(), 0, 0
    def count(value):
        nonlocal blocks, content_bytes
        if isinstance(value, dict):
            content = value.get('content')
            if isinstance(content, str):
                blocks += 1
                content_bytes += _bytes(content)
                identity = value.get('original_identity') or value.get('path') or value.get('identity')
                if isinstance(identity, str): files.add(identity)
            for child in value.values(): count(child)
        elif isinstance(value, list):
            for child in value: count(child)
    count(request)
    report = dict(stage=stage, request_id=request.get('unit_id') or request.get('subject_id') or request.get('operation_identity') or request.get('group_id'),
        decision='too_large' if total['characters']>limit else 'fits_budget', character_limit=limit,
        total=total, json_payload=_weight(encoded), instructions=_weight(instruction), components=components,
        json_envelope=dict(characters=len(encoded)-sum(item['characters'] for item in components.values()),
                           bytes=_bytes(encoded)-sum(item['bytes'] for item in components.values())),
        embedded_files=len(files), embedded_content_blocks=blocks, embedded_content_bytes=content_bytes,
        units='decimal: KB=1000 B; MB=1000000 B; GB=1000000000 B',
        scope='application JSON plus instructions; excludes provider transport envelope and tokenization')
    logger.log(logging.WARNING if total['characters']>limit else logging.INFO,
               'Model request size: %s', json.dumps(report, ensure_ascii=True, separators=(',',':')))
    from runtime.behavior_conversion.oversized_request_capture import save_oversized_request
    save_oversized_request(encoded, instruction, report)
    return report


def _bytes(text):
    # Preserve diagnostic availability even for legacy evidence with isolated UTF-16 surrogate code units.
    return len(text.encode('utf-8', errors='surrogatepass'))


def _weight(text):
    size = _bytes(text)
    return dict(characters=len(text), bytes=size, KB=round(size/1000,6), MB=round(size/1000000,9), GB=round(size/1000000000,12))
