from __future__ import annotations

import json
from pathlib import Path

from .classifier import DataflowClassifier
from .graphs import GraphBuilder
from .indexer import ComposerIndexer


class InternalIRBuilder:
    """Build deterministic internal IR for LLM generation and critic passes."""

    def __init__(self, source_root: Path, version: str) -> None:
        self.source_root = Path(source_root)
        self.version = version

    def build(self) -> dict:
        index_payload = ComposerIndexer(self.source_root, self.version).build()
        graph_payload = GraphBuilder(self.source_root, self.version).build()
        class_payload = DataflowClassifier(self.source_root, self.version).build()

        operations = index_payload["operations_catalog"]
        components = index_payload["component_catalog"]

        op_calls = self._adjacency(graph_payload["graph_operation_to_operation"]["edges"])
        op_components = self._adjacency(graph_payload["graph_operation_to_component"]["edges"])
        comp_deps = self._adjacency(graph_payload["graph_component_to_component"]["edges"])

        signatures = {
            "operations": [
                {
                    "name": name,
                    "attributes": operations[name]["attributes"],
                    "source": {
                        "file": operations[name]["file"],
                        "path": operations[name]["path"],
                    },
                }
                for name in sorted(operations)
            ],
            "components": [
                {
                    "name": name,
                    "attributes": components[name]["attributes"],
                    "source": {
                        "file": components[name]["file"],
                        "path": components[name]["path"],
                    },
                }
                for name in sorted(components)
            ],
        }

        data_flow = {
            "operation_calls": [{"from": s, "to": t} for s in sorted(op_calls) for t in op_calls[s]],
            "operation_component_usage": [{"from": s, "to": t} for s in sorted(op_components) for t in op_components[s]],
            "component_calls": [{"from": s, "to": t} for s in sorted(comp_deps) for t in comp_deps[s]],
        }

        side_effects = [
            {
                "actor": edge["source"],
                "field": edge["target"],
                "effect": edge["relationship"],
                "source": {"file": edge["file"], "path": edge["path"]},
            }
            for edge in graph_payload["graph_context_dependencies"]["edges"]
        ]

        dependency_contracts = {
            "field_classification": class_payload["field_classification"],
            "field_traces": class_payload["classification_traces"],
            "unknown_tag_queue": class_payload["llm_tag_interpretation_queue"],
        }

        return {
            "ir_schema_version": "1",
            "target": "composer_shared_components",
            "signatures": signatures,
            "data_flow": data_flow,
            "side_effects": side_effects,
            "dependency_contracts": dependency_contracts,
            "graph_diagnostics": graph_payload["graph_diagnostics"],
        }

    def persist(self, out_root: Path) -> Path:
        indexer = ComposerIndexer(self.source_root, self.version)
        source_hash = indexer.source_hash()
        artifact_dir = Path(out_root) / source_hash / self.version
        artifact_dir.mkdir(parents=True, exist_ok=True)
        payload = self.build()
        (artifact_dir / "internal_ir.json").write_text(
            json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return artifact_dir

    @staticmethod
    def _adjacency(edges: list[dict]) -> dict[str, list[str]]:
        data: dict[str, set[str]] = {}
        for edge in edges:
            data.setdefault(edge["source"], set()).add(edge["target"])
        return {key: sorted(value) for key, value in sorted(data.items())}


def build_internal_ir(source_root: str | Path, out_root: str | Path, version: str) -> Path:
    return InternalIRBuilder(Path(source_root), version).persist(Path(out_root))
