from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET

from .indexer import ComposerIndexer, SUPPORTED_EXTENSIONS

CLASSES = ("INPUT", "INTERMEDIATE", "ERROR", "OUTPUT")


@dataclass(frozen=True)
class ClassificationTrace:
    field: str
    classification: str
    rule: str
    evidence_path: str
    file: str


class DataflowClassifier:
    """Classify fields using deterministic graph traversal and XML semantics."""

    def __init__(self, source_root: Path, version: str) -> None:
        self.source_root = Path(source_root)
        self.version = version

    def build(self) -> dict:
        format_fields = self._collect_format_fields()
        read_fields, write_fields = self._collect_graph_reads_writes()

        traces: list[ClassificationTrace] = []
        fields = sorted(set(format_fields) | set(read_fields) | set(write_fields))
        for field in fields:
            traces.extend(self._classify_field(field, format_fields, read_fields, write_fields))

        assignments = {
            field: next(t.classification for t in traces if t.field == field)
            for field in fields
        }
        return {
            "field_classification": assignments,
            "classification_traces": [
                {
                    "field": t.field,
                    "classification": t.classification,
                    "rule": t.rule,
                    "evidence_path": t.evidence_path,
                    "file": t.file,
                }
                for t in traces
            ],
        }

    def persist(self, out_root: Path) -> Path:
        indexer = ComposerIndexer(self.source_root, self.version)
        source_hash = indexer.source_hash()
        artifact_dir = Path(out_root) / source_hash / self.version
        artifact_dir.mkdir(parents=True, exist_ok=True)

        payload = self.build()
        for name, data in payload.items():
            (artifact_dir / f"{name}.json").write_text(
                json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8"
            )
        return artifact_dir

    def _classify_field(self, field: str, format_fields: dict, read_fields: dict, write_fields: dict) -> list[ClassificationTrace]:
        has_read = field in read_fields
        has_write = field in write_fields

        if "error" in field.lower() or "fault" in field.lower():
            return [ClassificationTrace(field, "ERROR", "tag_semantic_error_name", *self._best_evidence(field, format_fields, read_fields, write_fields))]
        if has_read and not has_write:
            return [ClassificationTrace(field, "INPUT", "read_without_write", *self._best_evidence(field, format_fields, read_fields, write_fields))]
        if has_write and not has_read:
            return [ClassificationTrace(field, "OUTPUT", "write_without_read", *self._best_evidence(field, format_fields, read_fields, write_fields))]
        if has_read and has_write:
            return [ClassificationTrace(field, "INTERMEDIATE", "read_and_write", *self._best_evidence(field, format_fields, read_fields, write_fields))]
        return [ClassificationTrace(field, "INTERMEDIATE", "format_definition_only", *self._best_evidence(field, format_fields, read_fields, write_fields))]

    def _best_evidence(self, field: str, format_fields: dict, read_fields: dict, write_fields: dict) -> tuple[str, str]:
        if field in read_fields:
            return read_fields[field]["path"], read_fields[field]["file"]
        if field in write_fields:
            return write_fields[field]["path"], write_fields[field]["file"]
        entry = format_fields[field]
        return entry["path"], entry["file"]

    def _collect_format_fields(self) -> dict[str, dict[str, str]]:
        fields: dict[str, dict[str, str]] = {}
        for file_path in self._iter_source_files():
            rel = file_path.relative_to(self.source_root).as_posix()
            root = ET.parse(file_path).getroot()
            self._walk_format_fields(root, [], rel, fields)
        return fields

    def _walk_format_fields(self, node: ET.Element, ancestry: list[str], rel: str, fields: dict[str, dict[str, str]]) -> None:
        tag = self._normalize_tag(node.tag)
        path = "/".join(ancestry + [tag])
        if tag in {"field", "attribute", "element", "member"}:
            name = node.attrib.get("name") or node.attrib.get("id") or node.attrib.get("key")
            if name and name not in fields:
                fields[name] = {"file": rel, "path": path}
        for child in list(node):
            self._walk_format_fields(child, ancestry + [tag], rel, fields)

    def _collect_graph_reads_writes(self) -> tuple[dict[str, dict[str, str]], dict[str, dict[str, str]]]:
        reads: dict[str, dict[str, str]] = {}
        writes: dict[str, dict[str, str]] = {}
        for file_path in self._iter_source_files():
            rel = file_path.relative_to(self.source_root).as_posix()
            root = ET.parse(file_path).getroot()
            self._walk_reads_writes(root, [], rel, reads, writes)
        return reads, writes

    def _walk_reads_writes(self, node: ET.Element, ancestry: list[str], rel: str, reads: dict[str, dict[str, str]], writes: dict[str, dict[str, str]]) -> None:
        tag = self._normalize_tag(node.tag)
        path = "/".join(ancestry + [tag])
        is_read = "read" in tag or tag in {"source", "input"}
        is_write = "write" in tag or tag in {"target", "output"}

        for key, value in node.attrib.items():
            k = key.lower()
            if any(tok in k for tok in ("field", "context", "key", "name")):
                for raw in value.replace(",", " ").split():
                    token = raw.strip()
                    if not token:
                        continue
                    if is_read:
                        reads.setdefault(token, {"file": rel, "path": path})
                    if is_write:
                        writes.setdefault(token, {"file": rel, "path": path})

        for child in list(node):
            self._walk_reads_writes(child, ancestry + [tag], rel, reads, writes)

    def _iter_source_files(self) -> Iterable[Path]:
        files = [
            p for p in self.source_root.rglob("*") if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        return sorted(files, key=lambda p: p.relative_to(self.source_root).as_posix())

    @staticmethod
    def _normalize_tag(tag: str) -> str:
        if "}" in tag:
            tag = tag.split("}", 1)[1]
        return tag.strip().lower()


def build_classification(source_root: str | Path, out_root: str | Path, version: str) -> Path:
    return DataflowClassifier(Path(source_root), version).persist(Path(out_root))
