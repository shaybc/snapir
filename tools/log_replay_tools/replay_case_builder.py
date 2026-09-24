from __future__ import annotations

from models.validation_models import LogReplayCase


def build_replay_cases(
    log_entries: list[dict],
    operation_id: str,
    max_cases: int = 10,
) -> list[LogReplayCase]:
    """Select replay cases for one operation, preferring success and error coverage."""
    matching = [entry for entry in log_entries if entry.get("operation_name") == operation_id]
    selected: list[dict] = []
    success = next((entry for entry in matching if not _is_error_response(entry.get("response_xml", ""))), None)
    error = next((entry for entry in matching if _is_error_response(entry.get("response_xml", ""))), None)
    for candidate in (success, error):
        if candidate and candidate not in selected:
            selected.append(candidate)
    for entry in matching:
        if len(selected) >= max_cases:
            break
        if entry not in selected and _has_new_request_shape(entry, selected):
            selected.append(entry)
    return [
        LogReplayCase(
            operation_id=operation_id,
            raw_request_xml=entry["request_xml"],
            expected_response_xml=entry["response_xml"],
            source_log_ref=entry.get("source_log_ref") or entry.get("timestamp") or f"{operation_id}:{index}",
        )
        for index, entry in enumerate(selected[:max_cases], start=1)
    ]


def _is_error_response(response_xml: str) -> bool:
    return "error" in response_xml.lower()


def _has_new_request_shape(entry: dict, selected: list[dict]) -> bool:
    request = entry.get("request_xml", "")
    return request not in {item.get("request_xml", "") for item in selected}
