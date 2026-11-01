"""Budgets and integrity survive repair, split descendants and interrupted resumes."""
import pytest
from tests.runtime.test_behavior_conversion import state as connection
from tools.state_store_tools import metadata_checklist_state as state


def test_shared_limits_do_not_reset_with_reopen_split_or_changed_production():
    conn,_=connection();limits=dict(calls=3,transports=4,item_attempts=2)
    try:
        state.open_task(conn,'run','task',['a','b'],limits)
        state.reserve_call(conn,'run','task',['a','b'],limits)
        state.save_items(conn,'run','task','old',{'a':{'checklist_id':'a'}})
        assert state.accepted(conn,'run','task','new')=={}
        assert state.open_task(conn,'run','task',['b','a'],dict(calls=999,transports=999,item_attempts=999))==limits
        state.reserve_call(conn,'run','task',['a'],limits)
        with pytest.raises(ValueError,match='item attempt'):state.reserve_call(conn,'run','task',['a'],limits)
        assert conn.execute('SELECT calls FROM metadata_checklist_tasks').fetchone()[0]==2
        state.reserve_call(conn,'run','task',['b'],limits)
        with pytest.raises(ValueError,match='logical-call'):state.reserve_call(conn,'run','task',['b'],limits)
    finally:conn.close()


def test_item_proofs_are_intact_and_accepted_siblings_cannot_be_overwritten():
    conn,_=connection()
    try:
        state.open_task(conn,'r','t',['a'],dict(calls=2,transports=2,item_attempts=2))
        state.save_items(conn,'r','t','proof',{'a':{'value':1}})
        assert state.accepted(conn,'r','t','proof')=={'a':{'value':1}}
        with pytest.raises(ValueError,match='overwrite'):state.save_items(conn,'r','t','proof',{'a':{'value':2}})
        conn.execute("UPDATE metadata_checklist_items SET data_json='{}'")
        with pytest.raises(ValueError,match='integrity'):state.accepted(conn,'r','t','proof')
    finally:conn.close()


def test_transport_budget_counts_every_actual_attempt_before_provider_call():
    conn,_=connection();limits=dict(calls=2,transports=2,item_attempts=2)
    try:
        state.open_task(conn,'r','t',['a'],limits)
        call=state.reserve_call(conn,'r','t',['a'],limits)
        for n in (1,2):state.reserve_transport(conn,'r','t',call,n,{},limits)
        with pytest.raises(ValueError,match='transport'):state.reserve_transport(conn,'r','t',call,3,{},limits)
        assert conn.execute('SELECT count(*) FROM metadata_checklist_attempts').fetchone()[0]==2
    finally:conn.close()
