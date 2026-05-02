from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET

from .indexer import ComposerIndexer, SUPPORTED_EXTENSIONS


@dataclass(frozen=True)
class GraphEdge:
    source: str
    target: str
    relationship: str
    file: str
    path: str


class GraphConstructionError(RuntimeError):
    """Raised when graph construction fails."""


class GraphBuilder:
    """Build deterministic dependency graphs from Composer source artifacts."""

    def __init__(self, source_root: Path, version: str) -> None:
        self.source_root = Path(source_root)
        self.version = version

    def build(self) -> dict[str, dict]:
        operation_names, component_names = self._collect_symbols()

        op_to_component: list[GraphEdge] = []
        op_to_op: list[GraphEdge] = []
        component_to_component: list[GraphEdge] = []
        context_edges: list[GraphEdge] = []

        for file_path in self._iter_source_files():
            rel = file_path.relative_to(self.source_root).as_posix()
            try:
                root = ET.parse(file_path).getroot()
            except ET.ParseError as exc:
                raise GraphConstructionError(f"Unable to parse {file_path}") from exc

            self._walk_edges(
                node=root,
                ancestry=[],
                rel_path=rel,
                op_names=operation_names,
                component_names=component_names,
                op_to_component=op_to_component,
                op_to_op=op_to_op,
                component_to_component=component_to_component,
                context_edges=context_edges,
            )

        return {
            "graph_operation_to_component": self._serialize_edges(op_to_component),
            "graph_operation_to_operation": self._serialize_edges(op_to_op),
            "graph_component_to_component": self._serialize_edges(component_to_component),
            "graph_context_dependencies": self._serialize_edges(context_edges),
        }

    def persist(self, out_root: Path, include_adjacency_index: bool = True) -> Path:
        indexer = ComposerIndexer(self.source_root, self.version)
        source_hash = indexer.source_hash()
        artifact_dir = Path(out_root) / source_hash / self.version
        artifact_dir.mkdir(parents=True, exist_ok=True)

        payload = self.build()
        for name, data in payload.items():
            (artifact_dir / f"{name}.json").write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
            if include_adjacency_index:
                idx = self._build_adjacency_index(data)
                (artifact_dir / f"{name}_adjacency_index.json").write_text(
                    json.dumps(idx, indent=2, sort_keys=True) + "\n", encoding="utf-8"
                )

        return artifact_dir

    def _collect_symbols(self) -> tuple[set[str], set[str]]:
        index = ComposerIndexer(self.source_root, self.version).build()
        return set(index["operations_catalog"].keys()), set(index["component_catalog"].keys())

    def _walk_edges(
        self,
        node: ET.Element,
        ancestry: list[str],
        rel_path: str,
        op_names: set[str],
        component_names: set[str],
        op_to_component: list[GraphEdge],
        op_to_op: list[GraphEdge],
        component_to_component: list[GraphEdge],
        context_edges: list[GraphEdge],
    ) -> None:
        tag = self._normalize_tag(node.tag)
        path = "/".join(ancestry + [tag])
        node_name = node.attrib.get("name") or node.attrib.get("id")

        if node_name and tag == "operation":
            for ref in self._extract_refs(node.attrib):
                if ref in component_names:
                    op_to_component.append(GraphEdge(node_name, ref, "uses_component", rel_path, path))
                if ref in op_names:
                    op_to_op.append(GraphEdge(node_name, ref, "invokes_operation", rel_path, path))

        if node_name and tag in {"component", "sharedcomponent"}:
            for ref in self._extract_refs(node.attrib):
                if ref in component_names:
                    component_to_component.append(GraphEdge(node_name, ref, "uses_component", rel_path, path))

        context_name = node.attrib.get("context") or node.attrib.get("contextKey") or node.attrib.get("key")
        if context_name and ("read" in tag or "write" in tag or "context" in tag):
            actor = node.attrib.get("operation") or node.attrib.get("component") or node.attrib.get("name") or "unknown"
            dep = "read" if "read" in tag else "write" if "write" in tag else "touch"
            context_edges.append(GraphEdge(actor, context_name, f"context_{dep}", rel_path, path))

        for child in list(node):
            self._walk_edges(
                child,
                ancestry + [tag],
                rel_path,
                op_names,
                component_names,
                op_to_component,
                op_to_op,
                component_to_component,
                context_edges,
            )

    @staticmethod
    def _extract_refs(attrs: dict[str, str]) -> set[str]:
        refs: set[str] = set()
        for key, value in attrs.items():
            k = key.lower()
            if any(token in k for token in ("component", "operation", "target", "ref", "uses", "calls")):
                for item in value.replace(",", " ").split():
                    refs.add(item.strip())
        return refs

    @staticmethod
    def _normalize_tag(tag: str) -> str:
        if "}" in tag:
            tag = tag.split("}", 1)[1]
        return tag.strip().lower()

    def _iter_source_files(self) -> Iterable[Path]:
        files = [
            p for p in self.source_root.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        return sorted(files, key=lambda p: p.relative_to(self.source_root).as_posix())

    @staticmethod
    def _serialize_edges(edges: list[GraphEdge]) -> dict:
        ordered = sorted({(e.source, e.target, e.relationship, e.file, e.path) for e in edges})
        serialized = [
            {
                "source": s,
                "target": t,
                "relationship": r,
                "file": f,
                "path": p,
            }
            for s, t, r, f, p in ordered
        ]
        return {"edges": serialized, "count": len(serialized)}

    @staticmethod
    def _build_adjacency_index(graph: dict) -> dict[str, list[str]]:
        adjacency: dict[str, list[str]] = {}
        for edge in graph.get("edges", []):
            adjacency.setdefault(edge["source"], []).append(edge["target"])
        return {k: sorted(set(v)) for k, v in sorted(adjacency.items())}


def build_graphs(source_root: str | Path, out_root: str | Path, version: str, include_adjacency_index: bool = True) -> Path:
    return GraphBuilder(Path(source_root), version).persist(Path(out_root), include_adjacency_index)
