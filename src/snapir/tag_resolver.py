from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

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
        self._accepted_semantics: dict[str, dict[str, str | bool | float | dict]] = {}

    RESPONSE_SCHEMA_VERSION = "1.0"
    ALLOWED_SEMANTICS = ("field", "read", "write", "unknown", "ambiguous")

    @classmethod
    def response_contract_schema(cls) -> dict[str, object]:
        return {
            "$schema": "https://json-schema.org/draft/2020-12/schema",
            "type": "object",
            "additionalProperties": False,
            "required": ["normalized_tag", "semantic", "confidence", "rationale", "provenance"],
            "properties": {
                "normalized_tag": {"type": "string", "minLength": 1},
                "semantic": {"type": "string", "enum": list(cls.ALLOWED_SEMANTICS)},
                "confidence": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "rationale": {"type": "string", "minLength": 1},
                "provenance": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["model", "prompt_template", "response_schema_version"],
                    "properties": {
                        "model": {"type": "string", "minLength": 1},
                        "prompt_template": {"type": "string", "minLength": 1},
                        "response_schema_version": {"type": "string", "const": cls.RESPONSE_SCHEMA_VERSION},
                    },
                },
            },
        }

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
            self._unknown_queue.append(
                {
                    "tag": raw_tag,
                    "normalized": normalized,
                    "file": file,
                    "path": path,
                    "reason": resolution.reason,
                    "llm_contract": {
                        "response_schema": self.response_contract_schema(),
                        "retry_on_schema_invalid": True,
                        "max_retries": 2,
                    },
                }
            )

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

    @property
    def accepted_semantics(self) -> dict[str, dict[str, str | bool | float | dict]]:
        return dict(sorted(self._accepted_semantics.items()))

    def resolve_unknown_with_llm(self, response: dict[str, object], retry_count: int = 0) -> tuple[bool, str]:
        valid, reason = self._validate_contract_response(response)
        if not valid:
            if retry_count < 2:
                return False, f"schema_invalid_retry_{retry_count + 1}:{reason}"
            return False, f"schema_invalid_rejected:{reason}"

        normalized = str(response["normalized_tag"])
        semantic = str(response["semantic"])
        confidence = float(response["confidence"])
        rationale = str(response["rationale"])
        provenance = response["provenance"]
        replay_id = str(uuid4())
        accepted_at = datetime.now(timezone.utc).isoformat()

        self._accepted_semantics[normalized] = {
            "normalized_tag": normalized,
            "semantic": semantic,
            "requires_llm": False,
            "reason": "accepted_llm_resolution",
            "confidence": confidence,
            "rationale": rationale,
            "provenance": provenance,
            "replayability": {
                "replay_id": replay_id,
                "accepted_at_utc": accepted_at,
                "source_hash": ComposerIndexer(self.source_root, self.version).source_hash(),
                "version": self.version,
            },
        }
        return True, "accepted"

    def _validate_contract_response(self, response: dict[str, object]) -> tuple[bool, str]:
        required = {"normalized_tag", "semantic", "confidence", "rationale", "provenance"}
        if not required.issubset(response):
            return False, "missing_required_fields"
        if str(response.get("semantic")) not in self.ALLOWED_SEMANTICS:
            return False, "invalid_semantic"
        try:
            confidence = float(response.get("confidence"))
        except (TypeError, ValueError):
            return False, "confidence_not_numeric"
        if confidence < 0.0 or confidence > 1.0:
            return False, "confidence_out_of_range"
        provenance = response.get("provenance")
        if not isinstance(provenance, dict):
            return False, "invalid_provenance"
        prov_required = {"model", "prompt_template", "response_schema_version"}
        if not prov_required.issubset(provenance):
            return False, "missing_provenance_fields"
        if provenance.get("response_schema_version") != self.RESPONSE_SCHEMA_VERSION:
            return False, "invalid_schema_version"
        return True, "ok"

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
        (artifact_dir / "accepted_tag_semantics.json").write_text(
            json.dumps(self.accepted_semantics, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return artifact_dir
