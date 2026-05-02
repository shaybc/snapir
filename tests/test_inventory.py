from pathlib import Path
import json

import pytest

from snapir.inventory import (
    InventoryCoordinatorAgent,
    MalformedSourceArtifactError,
    MissingParseOutputError,
)


def test_inventory_coordinator_writes_inventory_and_checkpoints(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "a.xml").write_text("<root><operation name='CreateOrder'/></root>", encoding="utf-8")
    (source / "b.dse").write_text("<root><component name='Cache'/></root>", encoding="utf-8")

    out = tmp_path / "out"
    agent = InventoryCoordinatorAgent(source, out, version="v1")
    inventory_path = agent.run()

    assert inventory_path.name == "phase0_inventory.json"
    inventory = json.loads(inventory_path.read_text(encoding="utf-8"))
    assert inventory["phase"] == "phase0"
    assert "manifest.json" in inventory["outputs"]
    assert len(inventory["checkpoints"]) == 5

    checkpoints = json.loads((inventory_path.parent / "phase0_checkpoints.json").read_text(encoding="utf-8"))
    assert len(checkpoints["records"]) == 5


def test_inventory_coordinator_fails_on_malformed_source_artifact(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "bad.xml").write_text("<root><operation></root>", encoding="utf-8")

    agent = InventoryCoordinatorAgent(source, tmp_path / "out", version="v1")
    with pytest.raises(MalformedSourceArtifactError):
        agent.run()


def test_validate_parse_completeness_strictly_fails(tmp_path: Path) -> None:
    source = tmp_path / "src"
    source.mkdir()
    (source / "a.xml").write_text("<root><operation name='CreateOrder'/></root>", encoding="utf-8")

    agent = InventoryCoordinatorAgent(source, tmp_path / "out", version="v1")
    artifact_dir = tmp_path / "out" / "abc" / "v1"
    artifact_dir.mkdir(parents=True)
    (artifact_dir / "manifest.json").write_text("{}", encoding="utf-8")

    with pytest.raises(MissingParseOutputError):
        agent._validate_parse_completeness(artifact_dir)
