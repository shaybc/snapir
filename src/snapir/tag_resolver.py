from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .indexer import ComposerIndexer


KNOWN_TAG_MAPPING: dict[str, str] = {
    "field": "field",
    "attribute": "field",
    "element": "field",
    "member": "field",
    "contextread": "read",
    "read": "read",
    "source": "read",
    "input": "read",
    "contextwrite": "write",
    "write": "write",
    "target": "write",
    "output": "write",
}


@dataclass(frozen=True)
class TagResolution:
    raw_tag: str
    normalized_tag: str
    semantic: str
    requires_llm: bool
    reason: str


class TagSemanticResolver:
    """Resolve XML tags into normalized semantic classes for downstream phases."""

    def __init__(self, source_root: Path, version: str) -> None:
        self.source_root = Path(source_root)
        self.version = version
        self._dictionary: dict[str, dict[str, str | bool]] = {}
        self._unknown_queue: list[dict[str, str]] = []

    @staticmethod
    def normalize_tag(tag: str) -> str:
        if "}" in tag:
            tag = tag.split("}", 1)[1]
        return tag.strip().lower()

    @staticmethod
    def deterministic_transforms(tag: str) -> list[str]:
        compact = tag.replace("-", "").replace("_", "")
        return [tag, compact]

    def resolve(self, raw_tag: str, file: str = "", path: str = "") -> TagResolution:
        normalized = self.normalize_tag(raw_tag)
        candidates = self.deterministic_transforms(normalized)

        hits = {KNOWN_TAG_MAPPING[c] for c in candidates if c in KNOWN_TAG_MAPPING}
        if len(hits) == 1:
            semantic = next(iter(hits))
            resolution = TagResolution(raw_tag, normalized, semantic, False, "known_mapping")
        elif len(hits) > 1:
            semantic = "ambiguous"
            resolution = TagResolution(raw_tag, normalized, semantic, True, "ambiguous_known_mapping")
            self._unknown_queue.append({"tag": raw_tag, "normalized": normalized, "file": file, "path": path, "reason": resolution.reason})
        else:
            semantic = "unknown"
            resolution = TagResolution(raw_tag, normalized, semantic, True, "unknown_tag")
            self._unknown_queue.append({"tag": raw_tag, "normalized": normalized, "file": file, "path": path, "reason": resolution.reason})

        self._dictionary[normalized] = {
            "normalized_tag": normalized,
            "semantic": resolution.semantic,
            "requires_llm": resolution.requires_llm,
            "reason": resolution.reason,
        }
        return resolution

    @property
    def normalized_semantics_dictionary(self) -> dict[str, dict[str, str | bool]]:
        return dict(sorted(self._dictionary.items()))

    @property
    def unknown_queue(self) -> list[dict[str, str]]:
        return list(self._unknown_queue)

    def persist(self, out_root: Path) -> Path:
        source_hash = ComposerIndexer(self.source_root, self.version).source_hash()
        artifact_dir = Path(out_root) / source_hash / self.version
        artifact_dir.mkdir(parents=True, exist_ok=True)

        (artifact_dir / "normalized_tag_semantics.json").write_text(
            json.dumps(self.normalized_semantics_dictionary, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        (artifact_dir / "llm_tag_interpretation_queue.json").write_text(
            json.dumps(self.unknown_queue, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return artifact_dir
