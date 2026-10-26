"""Retry exhausted tasks on explicit Resume while retaining history and accepted results."""

import json

import pytest
from runtime.behavior_conversion.generation import generate, EvidenceSummary
from runtime.behavior_conversion.resume_budget import with_resume_budget
from runtime.behavior_conversion.runner import resume_behavior_pipeline
from tests.runtime.test_behavior_conversion import state, profile


def test_explicit_resume_retries_exhausted_task_keeps_feedback_and_reuses_acceptance():
    conn, config = state()
    settings = profile(max_agent_task_retries=3)
    requests = []
    @with_resume_budget
    def resume(model):
        return generate(conn, config, settings, "analysis", "failed-unit", "Analyze", {},
                        EvidenceSummary, model_call=model)
    def invalid(instruction, request):
        requests.append(json.loads(request))
        return "invalid JSON"
    with pytest.raises(ValueError, match="Invalid JSON"):
        resume(invalid)
    original = [tuple(row) for row in conn.execute("SELECT * FROM behavior_attempts ORDER BY attempt")]
    assert len(original) == 3
    def valid(instruction, request):
        requests.append(json.loads(request))
        return '{"findings": ["preserved behavior"]}'
    result, fingerprint = resume(valid)
    assert result.findings == ["preserved behavior"]
    assert len(requests) == 4
    assert requests[-1]["previous_model_response"] == "invalid JSON"
    assert "Invalid JSON" in requests[-1]["correction_feedback"]
    rows = [tuple(row) for row in conn.execute("SELECT * FROM behavior_attempts ORDER BY attempt")]
    assert rows[:3] == original
    assert conn.execute("SELECT attempt FROM behavior_attempts ORDER BY attempt DESC LIMIT 1").fetchone()[0] == 4
    cached, same_fingerprint = resume(lambda *args: pytest.fail("Accepted unit must be reused"))
    assert cached == result and same_fingerprint == fingerprint
    assert conn.execute("SELECT COUNT(*) FROM behavior_attempts").fetchone()[0] == 4


def test_each_resume_is_bounded_even_if_generation_is_called_again_internally():
    conn, config = state()
    calls = []
    def invalid(*args):
        calls.append(args)
        return "invalid JSON"
    @with_resume_budget
    def resume():
        with pytest.raises(ValueError, match="Invalid JSON"):
            generate(conn, config, profile(), "analysis", "failed", "Analyze", {}, EvidenceSummary, model_call=invalid)
        with pytest.raises(ValueError, match="correction limit"):
            generate(conn, config, profile(), "analysis", "failed", "Analyze", {}, EvidenceSummary, model_call=invalid)
    resume()
    assert len(calls) == profile().max_agent_task_retries
    resume()
    assert len(calls) == 2 * profile().max_agent_task_retries
    rows = conn.execute("SELECT attempt,response,error FROM behavior_attempts ORDER BY attempt").fetchall()
    assert [row["attempt"] for row in rows] == list(range(1, 2 * profile().max_agent_task_retries + 1))
    assert all(row["response"] == "invalid JSON" and row["error"] for row in rows)
    # The explicit Resume boundary must not leak into unrelated/internal calls.
    with pytest.raises(ValueError, match="correction limit"):
        generate(conn, config, profile(), "analysis", "failed", "Analyze", {}, EvidenceSummary, model_call=invalid)
    assert len(calls) == 2 * profile().max_agent_task_retries


def test_pipeline_resume_entry_point_retries_exhaustion_and_reuses_accepted_result(monkeypatch, tmp_path):
    conn, config = state()
    responses = []
    def model(*args):
        return responses.pop(0)
    def discover(*args):
        generate(conn, config, profile(), "analysis", "entry-unit", "Analyze", {},
                 EvidenceSummary, model_call=model)
        raise RuntimeError("Stop after entry-point budget check")
    monkeypatch.setattr("agents.migration_planning.agent.get_operations_for_planning", discover)
    responses[:] = ["invalid JSON"] * profile().max_agent_task_retries
    with pytest.raises(ValueError, match="Invalid JSON"):
        resume_behavior_pipeline(conn, config, profile(), tmp_path, model_call=model)
    assert not responses
    responses.append('{"findings": ["retry succeeded"]}')
    with pytest.raises(RuntimeError, match="entry-point budget check"):
        resume_behavior_pipeline(conn, config, profile(), tmp_path, model_call=model)
    assert not responses
    with pytest.raises(RuntimeError, match="entry-point budget check"):
        resume_behavior_pipeline(conn, config, profile(), tmp_path, model_call=model)
    assert conn.execute("SELECT COUNT(*) FROM behavior_attempts").fetchone()[0] == profile().max_agent_task_retries + 1
