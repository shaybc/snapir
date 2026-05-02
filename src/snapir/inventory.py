from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol
import xml.etree.ElementTree as ET

from .indexer import ComposerIndexer


class Phase0Tool(Protocol):
    def run(self, source_root: Path, out_root: Path, source_hash: str, version: str) -> Path:
        """Run one phase-0 tool and return the output file path."""


class InventoryError(RuntimeError):
    """Base error for inventory generation failures."""


class MalformedSourceArtifactError(InventoryError):
    """Raised when source artifacts are malformed and cannot be parsed."""


class MissingParseOutputError(InventoryError):
    """Raised when one or more phase-0 tool outputs are missing."""


@dataclass(frozen=True)
class IndexerPhase0Tool:
    output_name: str

    def run(self, source_root: Path, out_root: Path, source_hash: str, version: str) -> Path:
        artifact_dir = out_root / source_hash / version
        output_file = artifact_dir / self.output_name
        if not output_file.exists():
            raise MissingParseOutputError(f"Missing parse output: {output_file}")
        return output_file


class InventoryCoordinatorAgent:
    """Executes phase-0 parse/index tools and emits an inventory + checkpoints."""

    PHASE0_OUTPUTS = (
        "operations_catalog.json",
        "component_catalog.json",
        "file_to_entity_map.json",
        "normalized_symbol_table.json",
        "manifest.json",
    )

    def __init__(self, source_root: Path, out_root: Path, version: str) -> None:
        self.source_root = Path(source_root)
        self.out_root = Path(out_root)
        self.version = version

    def run(self) -> Path:
        self._validate_source_artifacts()

        indexer = ComposerIndexer(self.source_root, self.version)
        artifact_dir = indexer.persist(self.out_root)
        source_hash = artifact_dir.parent.name

        phase0_tools = [IndexerPhase0Tool(name) for name in self.PHASE0_OUTPUTS]
        checkpoints: list[dict] = []
        outputs: dict[str, str] = {}
        for idx, tool in enumerate(phase0_tools, start=1):
            output_path = tool.run(self.source_root, self.out_root, source_hash, self.version)
            outputs[tool.output_name] = output_path.relative_to(artifact_dir).as_posix()
            checkpoints.append(
                {
                    "step": idx,
                    "tool": tool.__class__.__name__,
                    "output": tool.output_name,
                    "status": "completed",
                }
            )

        self._validate_parse_completeness(artifact_dir)

        inventory = {
            "source_root": self.source_root.as_posix(),
            "source_hash": source_hash,
            "version": self.version,
            "phase": "phase0",
            "outputs": outputs,
            "checkpoints": checkpoints,
        }
        inventory_path = artifact_dir / "phase0_inventory.json"
        inventory_path.write_text(json.dumps(inventory, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        checkpoint_path = artifact_dir / "phase0_checkpoints.json"
        checkpoint_path.write_text(json.dumps({"records": checkpoints}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        return inventory_path

    def _validate_parse_completeness(self, artifact_dir: Path) -> None:
        missing = [name for name in self.PHASE0_OUTPUTS if not (artifact_dir / name).exists()]
        if missing:
            missing_csv = ", ".join(sorted(missing))
            raise MissingParseOutputError(f"Missing parse outputs: {missing_csv}")

    def _validate_source_artifacts(self) -> None:
        for path in self.source_root.rglob("*"):
            if path.is_file() and path.suffix.lower() in {".xml", ".dse"}:
                try:
                    ET.parse(path)
                except ET.ParseError as exc:
                    raise MalformedSourceArtifactError(f"Malformed source artifact: {path}") from exc
