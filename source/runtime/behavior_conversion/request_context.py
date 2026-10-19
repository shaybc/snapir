"""Construct bounded model evidence without silently dropping source content."""

import json
from runtime.composer_behavior_context import attach_composer_behavior


def encode_request(payload, instruction, limit):
    """Check all serialized evidence, schema and instructions against a character budget."""
    request = attach_composer_behavior(payload)
    encoded = json.dumps(request, ensure_ascii=False)
    if len(encoded) + len(instruction) > limit:
        from runtime.behavior_conversion.correction_payload import compact_correction
        request = compact_correction(request)
        encoded = json.dumps(request, ensure_ascii=False)
        if len(encoded) + len(instruction) > limit:
            raise ValueError("Behavior request exceeds its context budget; reduce the evidence unit or use incremental analysis")
    return request, encoded


def source_parts(source, limit):
    """Split full source on line boundaries, retaining all content and stable excerpt names."""
    parts, current = [], ""
    for line in source.content.splitlines(keepends=True):
        if len(line) > limit:
            raise ValueError("A source line exceeds the analysis budget: " + source.identity)
        if current and len(current) + len(line) > limit:
            parts.append(current)
            current = ""
        current += line
    if current:
        parts.append(current)
    return [dict(identity=source.identity, part=index + 1, total_parts=len(parts),
                 content_hash=source.content_hash, content=content) for index, content in enumerate(parts)]


def bundle_parts(data, instruction, schema, limit):
    """Pack supporting sources together, splitting only oversized evidence bundles."""
    from models.behavior_unit import SourceEvidence
    metadata = {key: value for key, value in data.items() if key != "sources"}
    def fits(sources):
        try:
            encode_request(dict(metadata, sources=sources, part=999999, total_parts=999999,
                                schema=schema), instruction, limit)
            return True
        except ValueError:
            return False
    if not fits([]):
        raise ValueError("Bundle XML and configuration exceed the context budget")
    groups, current = [], []
    for source in data["sources"]:
        pieces = [source]
        if not fits([source]):
            _, empty = encode_request(dict(metadata, sources=[], part=999999, total_parts=999999,
                                           schema=schema), instruction, limit)
            available = max(1, (limit - len(empty) - len(instruction)) // 6)
            pieces = source_parts(SourceEvidence.model_validate(source), available)
        for piece in pieces:
            if not fits(current + [piece]):
                if current:
                    groups.append(current)
                current = []
            if not fits([piece]):
                raise ValueError("Source excerpt exceeds the bundle context budget")
            current.append(piece)
    if current:
        groups.append(current)
    return [dict(metadata, sources=sources, part=index + 1, total_parts=len(groups))
            for index, sources in enumerate(groups)]
