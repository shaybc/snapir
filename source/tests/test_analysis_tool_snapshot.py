"""Unit receipts keep exact analysis bytes even when the default tool is rebuilt."""
import hashlib
import pytest
from tools.behavior_verification.tool_snapshot import snapshot_tool


def test_tool_rebuild_does_not_change_an_existing_snapshot(tmp_path):
    source=tmp_path/'default.jar';source.write_bytes(b'first analysis tool')
    first=snapshot_tool(source,tmp_path/'retained')
    assert first.stem==hashlib.sha256(source.read_bytes()).hexdigest()
    assert snapshot_tool(source,tmp_path/'retained')==first
    source.write_bytes(b'rebuilt analysis tool')
    second=snapshot_tool(source,tmp_path/'retained')
    assert first!=second and first.read_bytes()==b'first analysis tool'
    assert second.read_bytes()==b'rebuilt analysis tool'


def test_tampered_tool_snapshot_is_rejected_without_overwriting_it(tmp_path):
    source=tmp_path/'default.jar';source.write_bytes(b'analysis tool')
    target=snapshot_tool(source,tmp_path/'retained');target.write_bytes(b'tampered')
    with pytest.raises(ValueError,match='snapshot changed'):snapshot_tool(source,tmp_path/'retained')
    assert target.read_bytes()==b'tampered'


def test_tool_change_during_snapshot_is_rejected(tmp_path,monkeypatch):
    import tools.behavior_verification.tool_snapshot as module
    source=tmp_path/'default.jar';source.write_bytes(b'analysis tool');link=module.os.link
    def changed(*args):
        link(*args);source.write_bytes(b'changed during snapshot')
    monkeypatch.setattr(module.os,'link',changed)
    with pytest.raises(ValueError,match='while creating'):snapshot_tool(source,tmp_path/'retained')
