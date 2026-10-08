from __future__ import annotations

from models.conversion_models import ValidationFailureClass
from models.validation_models import ContextAccess, ExecutionTrace, StepTrace
from tools.trace_comparator_tools.trace_comparator_tool import compare_traces


def trace(
    *,
    step_ids: list[str] | None = None,
    rcs: list[int] | None = None,
    write_value: str | None = "ok",
    final_xml: str = "<response><id>1</id></response>",
) -> ExecutionTrace:
    step_ids = step_ids or ["StepA", "StepB"]
    rcs = rcs or [0, 0]
    return ExecutionTrace(
        operation_id="TransferFunds",
        channel="INTERNET",
        scenario="success",
        request_xml="<request />",
        steps_executed=[
            StepTrace(
                step_id=step_id,
                step_index=index,
                impl_class=step_id,
                return_code=rcs[index],
                context_writes=[
                    ContextAccess(field_name="accountId", value_after=write_value, context_level="TransferContext")
                ]
                if write_value is not None
                else [],
                routing_rule_used="test",
            )
            for index, step_id in enumerate(step_ids)
        ],
        selected_reply_format="Reply",
        reply_format_switched=False,
        final_xml=final_xml,
    )


def test_identical_traces_match():
    result = compare_traces(trace(), trace())

    assert result.matched is True
    assert result.failure_class is None


def test_different_step_sequence_is_routing_mismatch():
    result = compare_traces(trace(), trace(step_ids=["StepA", "StepC"]))

    assert result.step_sequence_match is False
    assert result.failure_class == ValidationFailureClass.routing_mismatch


def test_same_sequence_different_rc_is_routing_mismatch():
    result = compare_traces(trace(), trace(rcs=[0, 4]))

    assert result.rc_per_step_match is False
    assert result.failure_class == ValidationFailureClass.routing_mismatch


def test_same_sequence_missing_context_write_is_conversion_gap():
    result = compare_traces(trace(), trace(write_value=None))

    assert result.context_writes_match is False
    assert result.failure_class == ValidationFailureClass.conversion_gap


def test_same_sequence_matching_context_different_final_xml_is_equivalence_gap():
    result = compare_traces(trace(), trace(final_xml="<response><id>2</id></response>"))

    assert result.final_xml_match is False
    assert result.failure_class == ValidationFailureClass.equivalence_gap


def test_different_sequence_and_final_xml_is_routing_mismatch():
    result = compare_traces(
        trace(),
        trace(step_ids=["StepA", "StepC"], final_xml="<response><id>2</id></response>"),
    )

    assert result.failure_class == ValidationFailureClass.routing_mismatch
