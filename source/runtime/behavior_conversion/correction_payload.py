"""Deduplicate oversized correction requests without discarding source evidence."""

from copy import deepcopy
import json

from runtime.managed_conversion_response import _remove_response_fence


def compact_correction(payload):
    """Return a copy with duplicate candidate contents pointing to retained failed sources.

    Complete sources, diagnostics and accepted APIs remain in this request. Original
    provider responses and errors are preserved by the caller's attempt history.
    """
    if not (payload.get("compiler_correction") or payload.get("test_correction")):
        return payload
    result = deepcopy(payload)
    if result.get("test_correction"):
        from runtime.behavior_conversion.test_correction_payload import trim_test_correction
        result = trim_test_correction(result)
    sources = {}
    changed = False
    for field in ("compiler_correction", "test_correction"):
        correction = result.get(field, {})
        for collection in ("failed_sources", "relevant_implementation_sources"):
            for index, source in enumerate(correction.get(collection, [])):
                if source.get("content"):
                    sources[(source.get("path"), source["content"])] = f"{field}.{collection}[{index}].content"
    try:
        candidate = json.loads(_remove_response_fence(result.get("previous_model_response", "")))
    except (ValueError, TypeError):
        candidate = None
    if isinstance(candidate, dict):
        for file in candidate.get("files", []):
            reference = sources.get((file.get("path"), file.get("content")))
            if reference:
                file.pop("content")
                file["content_ref"] = reference
                changed = True
        if changed:
            result["previous_model_response"] = json.dumps(candidate, ensure_ascii=False)
    for field in ("compiler_correction", "test_correction"):
        correction = result.get(field, {})
        if correction.get("original_compiler_output") == result.get("correction_feedback") and result.get("correction_feedback"):
            correction.pop("original_compiler_output")
            correction["original_compiler_output_ref"] = "correction_feedback"
            changed = True
    if changed:
        result["correction_content_references"] = (
            "content_ref and original_compiler_output_ref identify exact retained values in this same JSON request. "
            "Read that value at the named field instead of a duplicate copy. Sources have not been truncated. "
            "Return complete corrected files with content, never content_ref, in the response schema.")
    return result
