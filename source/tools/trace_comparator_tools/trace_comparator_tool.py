from __future__ import annotations

from models.conversion_models import ValidationFailureClass
from models.validation_models import (
    ContextWriteMismatch,
    ExecutionTrace,
    RcMismatch,
    TraceComparisonResult,
)
from tools.validation_tools.xml_diff_tool import compare_xml


def compare_traces(
    legacy: ExecutionTrace,
    generated: ExecutionTrace,
) -> TraceComparisonResult:
    """Compare legacy and generated execution traces field by field."""
    legacy_sequence = [step.step_id for step in legacy.steps_executed]
    generated_sequence = [step.step_id for step in generated.steps_executed]
    step_sequence_diff = _sequence_diff(legacy_sequence, generated_sequence)
    step_sequence_match = legacy_sequence == generated_sequence
    rc_mismatches = _rc_mismatches(legacy, generated)
    context_mismatches = _context_write_mismatches(legacy, generated)
    reply_format_mismatch = _reply_format_mismatch(legacy, generated)
    xml_diff = compare_xml(legacy.final_xml, generated.final_xml)
    rc_per_step_match = not rc_mismatches
    context_writes_match = not context_mismatches
    reply_format_match = reply_format_mismatch is None
    final_xml_match = xml_diff.passed
    matched = all(
        [
            step_sequence_match,
            rc_per_step_match,
            context_writes_match,
            reply_format_match,
            final_xml_match,
        ]
    )
    return TraceComparisonResult(
        matched=matched,
        step_sequence_match=step_sequence_match,
        rc_per_step_match=rc_per_step_match,
        context_writes_match=context_writes_match,
        reply_format_match=reply_format_match,
        final_xml_match=final_xml_match,
        step_sequence_diff=step_sequence_diff,
        rc_mismatches=rc_mismatches,
        context_write_mismatches=context_mismatches,
        reply_format_mismatch=reply_format_mismatch,
        final_xml_diff=xml_diff.diffs,
        failure_class=_failure_class(
            step_sequence_match,
            rc_per_step_match,
            context_writes_match,
            reply_format_match,
            final_xml_match,
        ),
    )


def _sequence_diff(legacy_sequence: list[str], generated_sequence: list[str]) -> list[str]:
    if legacy_sequence == generated_sequence:
        return []
    diffs = []
    for step_id in legacy_sequence:
        if step_id not in generated_sequence:
            diffs.append(f"missing generated step: {step_id}")
    for step_id in generated_sequence:
        if step_id not in legacy_sequence:
            diffs.append(f"extra generated step: {step_id}")
    if not diffs:
        diffs.append(f"order differs legacy={legacy_sequence} generated={generated_sequence}")
    return diffs


def _rc_mismatches(legacy: ExecutionTrace, generated: ExecutionTrace) -> list[RcMismatch]:
    mismatches = []
    for legacy_step, generated_step in zip(legacy.steps_executed, generated.steps_executed):
        if legacy_step.step_id != generated_step.step_id:
            continue
        if legacy_step.return_code != generated_step.return_code:
            mismatches.append(
                RcMismatch(
                    step_id=legacy_step.step_id,
                    legacy_rc=legacy_step.return_code,
                    generated_rc=generated_step.return_code,
                )
            )
    return mismatches


def _context_write_mismatches(
    legacy: ExecutionTrace,
    generated: ExecutionTrace,
) -> list[ContextWriteMismatch]:
    mismatches = []
    for legacy_step, generated_step in zip(legacy.steps_executed, generated.steps_executed):
        if legacy_step.step_id != generated_step.step_id:
            continue
        generated_writes = {write.field_name: write for write in generated_step.context_writes}
        for legacy_write in legacy_step.context_writes:
            generated_write = generated_writes.get(legacy_write.field_name)
            if generated_write is None or legacy_write.value_after != generated_write.value_after:
                mismatches.append(
                    ContextWriteMismatch(
                        step_id=legacy_step.step_id,
                        field_name=legacy_write.field_name,
                        legacy_value=legacy_write.value_after,
                        generated_value=generated_write.value_after if generated_write else None,
                    )
                )
    return mismatches


def _reply_format_mismatch(legacy: ExecutionTrace, generated: ExecutionTrace) -> str | None:
    if legacy.selected_reply_format != generated.selected_reply_format:
        return (
            "selected_reply_format differs "
            f"legacy={legacy.selected_reply_format} generated={generated.selected_reply_format}"
        )
    if legacy.reply_format_switched != generated.reply_format_switched:
        return (
            "reply_format_switched differs "
            f"legacy={legacy.reply_format_switched} generated={generated.reply_format_switched}"
        )
    return None


def _failure_class(
    step_sequence_match: bool,
    rc_per_step_match: bool,
    context_writes_match: bool,
    reply_format_match: bool,
    final_xml_match: bool,
) -> ValidationFailureClass | None:
    if not step_sequence_match or not rc_per_step_match or not reply_format_match:
        return ValidationFailureClass.routing_mismatch
    if not context_writes_match and step_sequence_match:
        return ValidationFailureClass.conversion_gap
    if not final_xml_match and step_sequence_match and rc_per_step_match:
        return ValidationFailureClass.equivalence_gap
    if not final_xml_match and not step_sequence_match:
        return ValidationFailureClass.routing_mismatch
    return None
