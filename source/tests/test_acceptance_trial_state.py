"""A model-change trial keeps failed-call budgets and never inherits acceptance or edits history."""
import hashlib
import json
import sqlite3
import pytest
from tools.behavior_verification.acceptance_trial_state import inherit_provider_attempts
from tools.state_store_tools import staged_conversion_state as stages
from tools.state_store_tools.behavior_units import initialize


def previous(tmp_path):
    folder=tmp_path/'prior';folder.mkdir()
    (folder/'acceptance-trials.json').write_text(json.dumps({'status':'blocked','operation':'INTERNET/GetClientLinksOp'}))
    conn=sqlite3.connect(folder/'trials.db');initialize(conn)
    stages.reserve(conn,'bank-executable-acceptance','unit','revision','implementation',4,{})
    stages.finish(conn,'bank-executable-acceptance','unit','revision','implementation',1,error='provider unavailable')
    conn.close();return folder


def test_provider_counters_survive_model_change_without_modifying_prior(tmp_path):
    prior=previous(tmp_path);before=hashlib.sha256((prior/'trials.db').read_bytes()).hexdigest()
    target=tmp_path/'new';target.mkdir();proof=inherit_provider_attempts(prior,target)
    conn=sqlite3.connect(target/'trials.db')
    try:assert stages.reserve(conn,'bank-executable-acceptance','unit','revision','implementation',4,{'model':'lite'})==2
    finally:conn.close()
    assert proof['inherited_role_counters'][0]['attempts']==1 and not proof['acceptance_inherited']
    assert hashlib.sha256((prior/'trials.db').read_bytes()).hexdigest()==before


def test_cannot_relocate_successful_candidate_artifacts(tmp_path):
    prior=previous(tmp_path);conn=sqlite3.connect(prior/'trials.db')
    conn.execute("INSERT INTO behavior_attempts VALUES ('r','unit','u','f',1,'{}','candidate',NULL,'now')");conn.commit();conn.close()
    target=tmp_path/'new';target.mkdir()
    with pytest.raises(ValueError,match='cannot relocate'):inherit_provider_attempts(prior,target)
    assert not (target/'trials.db').exists()


def test_revision_changes_cannot_replenish_inherited_budget(tmp_path):
    from tools.behavior_verification.acceptance_trial_state import enforce_inherited_budget
    from runtime.behavior_conversion.verification_feedback import VerificationIncomplete
    prior=previous(tmp_path);conn=sqlite3.connect(prior/'trials.db')
    try:
        stages.reserve(conn,'bank-executable-acceptance','unit','new-revision','implementation',2,{})
        enforce_inherited_budget(conn,'bank-executable-acceptance','unit',2)
        stages.reserve(conn,'bank-executable-acceptance','unit','third-revision','implementation',2,{})
        with pytest.raises(VerificationIncomplete,match='Inherited implementation attempt budget exhausted'):
            enforce_inherited_budget(conn,'bank-executable-acceptance','unit',2)
        assert stages.read(conn,'bank-executable-acceptance','unit','third-revision','implementation')['status']=='failed'
    finally:conn.close()
