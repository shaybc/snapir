"""Check mock planning against the actual state store and planning validator."""

from models.pipeline_configuration import PipelineConfiguration
from runtime.planning import prepare_plan
from tests.test_migration_planning import memory_conn, run_config, seed_operations


def test_mock_planning_persists_small_scope():
    conn = memory_conn()
    seed_operations(conn, ["OpA"])
    profile = PipelineConfiguration(source_root="source", mapper_jar="mapper", output_root="output",
                                    channels=["INTERNET"], model_provider="mock")
    plan = prepare_plan(conn, run_config(), profile, [{"operation_id": "OpA", "channel": "INTERNET"}])
    assert plan.total_operations == 1
    assert conn.execute("SELECT COUNT(*) FROM migration_plans").fetchone()[0] == 1
    conn.close()
