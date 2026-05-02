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

        conversion_plan = self._build_component_conversion_plan(components, op_components, comp_deps)
        operation_ir = self._build_operation_ir(operations, op_calls)

        return {
            "ir_schema_version": "1",
            "target": "composer_shared_components",
            "signatures": signatures,
            "data_flow": data_flow,
            "side_effects": side_effects,
            "dependency_contracts": dependency_contracts,
            "shared_component_conversion_plan": conversion_plan,
            "operation_ir": operation_ir,
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

    @staticmethod
    def _build_component_conversion_plan(
        components: dict[str, dict],
        op_components: dict[str, list[str]],
        comp_deps: dict[str, list[str]],
    ) -> dict:
        """Prioritize shared-component conversion by reuse while respecting dependency order."""
        component_names = sorted(components)
        if not component_names:
            return {"ordered_components": [], "reuse_scores": {}, "constraints": {"blocked_cycles": []}}

        reuse_scores: dict[str, int] = {name: 0 for name in component_names}
        for used in op_components.values():
            for component in used:
                if component in reuse_scores:
                    reuse_scores[component] += 1
        for source, targets in comp_deps.items():
            if source in reuse_scores:
                reuse_scores[source] += len(targets)
            for target in targets:
                if target in reuse_scores:
                    reuse_scores[target] += 1

        # Build DAG orientation: dependency -> dependent.
        incoming: dict[str, set[str]] = {name: set() for name in component_names}
        outgoing: dict[str, set[str]] = {name: set() for name in component_names}
        for dependent, deps in comp_deps.items():
            if dependent not in outgoing:
                continue
            for dep in deps:
                if dep not in outgoing:
                    continue
                outgoing[dep].add(dependent)
                incoming[dependent].add(dep)

        queue = [name for name in component_names if not incoming[name]]
        ordered_components: list[dict[str, int | str]] = []

        while queue:
            queue.sort(key=lambda name: (-reuse_scores[name], name))
            node = queue.pop(0)
            ordered_components.append({"name": node, "reuse_score": reuse_scores[node]})
            for nxt in sorted(outgoing[node]):
                incoming[nxt].discard(node)
                if not incoming[nxt]:
                    queue.append(nxt)
            outgoing[node].clear()

        blocked_cycles = sorted(name for name in component_names if incoming[name])
        return {
            "ordered_components": ordered_components,
            "reuse_scores": {name: reuse_scores[name] for name in component_names},
            "constraints": {"blocked_cycles": blocked_cycles},
        }

    @classmethod
    def _build_operation_ir(cls, operations: dict[str, dict], op_calls: dict[str, list[str]]) -> dict:
        steps = []
        transitions = []
        external_calls = []

        operation_names = set(operations)
        for name in sorted(operations):
            attrs = operations[name]["attributes"]
            steps.append(
                {
                    "id": name,
                    "source": {"file": operations[name]["file"], "path": operations[name]["path"]},
                    "transformations": cls._match_tokens(attrs, ("transform", "map", "normalize", "convert")),
                    "error_handlers": cls._match_tokens(attrs, ("onerror", "error", "fault", "catch", "handler")),
                    "external_calls": cls._external_targets(attrs, operation_names),
                }
            )

            if name in op_calls and len(op_calls[name]) > 1:
                transitions.append({"from": name, "type": "branch", "to": op_calls[name]})
            elif name in op_calls and op_calls[name]:
                transitions.append({"from": name, "type": "next", "to": op_calls[name]})

            for target in cls._external_targets(attrs, operation_names):
                external_calls.append({"operation": name, "target": target})

        return {
            "schema_version": "1",
            "step_graph": {
                "steps": steps,
                "transitions": transitions,
            },
            "routing": {
                "branches": [t for t in transitions if t["type"] == "branch"],
                "linear": [t for t in transitions if t["type"] == "next"],
            },
            "external_calls": external_calls,
        }

    @staticmethod
    def _match_tokens(attrs: dict[str, str], hints: tuple[str, ...]) -> list[dict[str, str]]:
        hits: list[dict[str, str]] = []
        for key, value in sorted(attrs.items()):
            lowered = key.lower()
            if any(hint in lowered for hint in hints):
                hits.append({"attribute": key, "value": value})
        return hits

    @staticmethod
    def _external_targets(attrs: dict[str, str], operation_names: set[str]) -> list[str]:
        external: set[str] = set()
        for key, value in sorted(attrs.items()):
            lowered = key.lower()
            if not any(token in lowered for token in ("url", "uri", "endpoint", "service", "host", "http")):
                continue
            if value not in operation_names:
                external.add(value)
        return sorted(external)


def build_internal_ir(source_root: str | Path, out_root: str | Path, version: str) -> Path:
    return InternalIRBuilder(Path(source_root), version).persist(Path(out_root))
