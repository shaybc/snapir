"""Offline acceptance tests for published services and pinned run contracts."""
import copy
import pytest
import yaml
from pydantic import ValidationError
from runtime.configuration import load_configuration
from tools.converted_service_registry_tools.registry import open_registry, publish_service, get_service, list_services
from tools.state_store_tools.db import get_connection
from tools.state_store_tools.service_api_uses import record_service_use, get_service_use, list_service_uses

@pytest.fixture
def contract():
    return dict(application_id="bank", channel="WEB", operation_id="GetLinks", api_revision="1",
                service_id="links", artifact_reference="links.zip", method="POST", path="/links",
                media_types=["application/xml"], request_contract={"root": "request"},
                response_contract={"root": "response"}, error_contract={"codes": ["NOT_FOUND"]},
                api_definition={"openapi": "3.0.3"},
                addresses={"test": {"base_url": "http://localhost:8081", "port": 8081},
                           "prod": {"base_url_property": "LINKS_URL"}},
                completion=dict(source_run_id="first", validation_report_reference="tests.json",
                                conversion_passed=True, package_passed=True, tests_passed=True,
                                review_approved=True, gates_approved=True))

@pytest.mark.parametrize("flag", ["conversion_passed", "package_passed", "tests_passed", "review_approved", "gates_approved"])
@pytest.mark.parametrize("missing", [True, False])
def test_completion_required(tmp_path, contract, flag, missing):
    if missing:
        del contract["completion"][flag]
    else:
        contract["completion"][flag] = False
    with open_registry(tmp_path / "registry.db") as registry:
        with pytest.raises(ValidationError):
            publish_service(registry, contract)
        assert list_services(registry, "bank") == []

@pytest.mark.parametrize("field,value", [("status", "planned"), ("status", "assembled"), ("status", "failed"),
                                          ("request_contract", {}), ("api_definition", {}), ("addresses", {"test": {}})])
def test_invalid_records_rejected(tmp_path, contract, field, value):
    contract[field] = value
    with open_registry(tmp_path / "registry.db") as registry:
        with pytest.raises(ValidationError):
            publish_service(registry, contract)

def test_revisions_and_identity(tmp_path, contract):
    with open_registry(tmp_path / "registry.db") as registry:
        first = publish_service(registry, contract)
        assert publish_service(registry, contract) == first
        changed = copy.deepcopy(contract)
        changed["path"] = "/changed"
        with pytest.raises(ValueError, match="immutable"):
            publish_service(registry, changed)
        changed["api_revision"] = "2"
        publish_service(registry, changed)
        publish_service(registry, contract)
        assert get_service(registry, "bank", "WEB", "GetLinks").api_revision == "2"
        assert get_service(registry, "bank", "WEB", "GetLinks", api_revision="1") == first
        assert get_service(registry, "other", "WEB", "GetLinks") is None
        assert get_service(registry, "bank", "OTHER", "GetLinks") is None
        assert len(list_services(registry, "bank", channel="WEB")) == 2
        assert list_services(registry, "other") == []

def test_runs_keep_their_saved_contracts(tmp_path, contract):
    registry = open_registry(tmp_path / "registry.db")
    one = get_connection(str(tmp_path / "one.db"))
    two = get_connection(str(tmp_path / "two.db"))
    try:
        first = publish_service(registry, contract)
        pinned = record_service_use(one, "one", first, "test")
        assert record_service_use(one, "one", first, "test") == pinned
        contract["api_revision"] = "2"
        latest = publish_service(registry, contract)
        record_service_use(two, "two", latest, "prod")
        with pytest.raises(ValueError, match="another API"):
            record_service_use(one, "one", latest, "test")
        with pytest.raises(ValueError, match="another API"):
            record_service_use(one, "one", first, "prod")
        with pytest.raises(ValueError, match="no address"):
            record_service_use(one, "missing", latest, "unknown")
        assert get_service_use(one, "one", "bank", "WEB", "GetLinks") == pinned
        first.request_contract["root"] = "mutated"
        assert list_service_uses(one, "one")[0].contract.request_contract["root"] == "request"
        assert list_service_uses(two, "two")[0].contract.api_revision == "2"
        assert list_service_uses(one, "missing") == []
    finally:
        one.close()
        two.close()
        registry.close()
    (tmp_path / "one.db").unlink()
    with open_registry(tmp_path / "registry.db") as registry:
        assert get_service(registry, "bank", "WEB", "GetLinks").api_revision == "2"

def test_database_roles_separate(tmp_path, contract):
    run_path = tmp_path / "run.db"
    run = get_connection(str(run_path))
    run.execute("CREATE TABLE runs (id TEXT)")
    run.commit()
    run.close()
    with pytest.raises(ValueError, match="separate"):
        open_registry(run_path)
    with open_registry(tmp_path / "registry.db") as registry:
        with pytest.raises(ValueError, match="separate"):
            record_service_use(registry, "run", contract, "test")
        assert not registry.execute("SELECT 1 FROM sqlite_master WHERE name='service_api_uses'").fetchone()

def test_configuration_shared_location(tmp_path, monkeypatch):
    (tmp_path / "source").mkdir()
    (tmp_path / "mapper.jar").touch()
    path = tmp_path / "profile.yaml"
    profile = dict(source_root="source", mapper_jar="mapper.jar", conversion_strategy="behavior_units",
                   source_workspace_id="bank", output_root="one")
    path.write_text(yaml.safe_dump(profile))
    first = load_configuration(path)
    profile["output_root"] = "two"
    path.write_text(yaml.safe_dump(profile))
    monkeypatch.chdir(tmp_path / "source")
    assert load_configuration(path).service_registry_path == first.service_registry_path
    assert 'service_registry_path' in first.model_dump_json()
    profile["service_registry_path"] = "shared/services.db"
    path.write_text(yaml.safe_dump(profile))
    assert load_configuration(path).service_registry_path == str((tmp_path / "shared/services.db").resolve())
    assert not (tmp_path / "shared").exists()
    del profile["service_registry_path"]
    profile["source_workspace_id"] = "other-bank"
    path.write_text(yaml.safe_dump(profile))
    assert load_configuration(path).service_registry_path != first.service_registry_path
    del profile["source_workspace_id"]
    path.write_text(yaml.safe_dump(profile))
    assert load_configuration(path).source_workspace_id == (tmp_path / "source").as_uri()

def test_application_and_channel_records_are_independent(tmp_path, contract):
    with open_registry(tmp_path / "registry.db") as registry:
        publish_service(registry, contract)
        other = copy.deepcopy(contract)
        other["application_id"] = "other"
        other["path"] = "/other"
        publish_service(registry, other)
        other["application_id"] = "bank"
        other["channel"] = "IVR"
        publish_service(registry, other)
        assert get_service(registry, "bank", "WEB", "GetLinks").path == "/links"
        assert get_service(registry, "other", "WEB", "GetLinks").path == "/other"
        assert len(list_services(registry, "bank")) == 2
        assert len(list_services(registry, "bank", channel="WEB")) == 1


def test_existing_legacy_profile_keeps_registry_unconfigured(tmp_path):
    (tmp_path / "source").mkdir()
    (tmp_path / "mapper.jar").touch()
    path = tmp_path / "legacy.yaml"
    path.write_text(yaml.safe_dump(dict(source_root="source", mapper_jar="mapper.jar",
                                        conversion_strategy="legacy_components")))
    assert load_configuration(path).service_registry_path is None
