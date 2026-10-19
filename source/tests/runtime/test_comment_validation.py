"""Replay the model response rejected for quoted IBM names in JavaDoc."""

import json
from pathlib import Path
import pytest
from models.native_unit_bundle import NativeUnitBundle
from runtime.behavior_conversion.bundle_output import validate_bundle
from runtime.behavior_conversion.runner import _dependency_validation_version
from tools.state_store_tools.behavior_units import save
from tests.runtime.test_behavior_conversion import state


def test_latest_javadoc_response_passes_without_removing_documentation():
    raw = (Path(__file__).parent / 'fixtures/latest_javadoc_rejection.json').read_text(encoding='utf-8')
    bundle = NativeUnitBundle.model_validate_json(raw)
    original = bundle.model_dump_json()
    assert any('implClass="com.ibm.' in item.content for item in bundle.files)
    assert validate_bundle(bundle, bundle.unit_contract.apis, evidence_ids=bundle.unit_contract.evidence_ids)
    assert bundle.model_dump_json() == original


def test_unrelated_coverage_check_remains_strict_for_latest_response():
    raw = (Path(__file__).parent / 'fixtures/latest_javadoc_rejection.json').read_text(encoding='utf-8')
    bundle = NativeUnitBundle.model_validate_json(raw)
    with pytest.raises(ValueError, match='No executable test covers requirement: business'):
        validate_bundle(bundle, bundle.unit_contract.apis, bundle.unit_contract.requirements,
                        bundle.unit_contract.evidence_ids)


def test_latest_response_still_rejects_real_runtime_class_lookup():
    raw = (Path(__file__).parent / 'fixtures/latest_javadoc_rejection.json').read_text(encoding='utf-8')
    bundle = NativeUnitBundle.model_validate_json(raw)
    file = next(item for item in bundle.files if item.path.startswith('src/main/java/'))
    position = file.content.rfind('}')
    file.content = file.content[:position] + 'public Class<?> lookup() throws Exception { return Class.forName("com.ibm.Legacy"); }' + file.content[position:]
    with pytest.raises(ValueError, match='Prohibited framework dependency'):
        validate_bundle(bundle, bundle.unit_contract.apis)


def test_comment_validation_refreshes_only_unaccepted_legacy_requests():
    conn, config = state()
    save(conn, config.run_id, 'unit', 'accepted', 'existing', {})
    save(conn, config.run_id, 'unit', 'failed', 'existing', {}, 'failed', 'Prohibited framework dependency')
    for identity in ('accepted', 'failed'):
        payload = {}
        _dependency_validation_version(conn, config.run_id, 'unit', identity, payload,
                                       'source_comment_validation', 'comments-ignored-v1')
        assert ('source_comment_validation' in payload) == (identity == 'failed')
