from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET

SUPPORTED_EXTENSIONS = {".xml", ".dse"}
ENTITY_HINTS = {
    "operation": "operation",
    "component": "component",
    "sharedcomponent": "component",
    "format": "format",
}


@dataclass(frozen=True)
class ArtifactKey:
    source_hash: str
    version: str


class ComposerIndexer:
    """Build deterministic catalogs and symbol tables for Composer artifacts."""

    def __init__(self, source_root: Path, version: str) -> None:
        self.source_root = source_root
        self.version = version

    def source_hash(self) -> str:
        hasher = hashlib.sha256()
        for file_path in self._iter_source_files():
            rel = file_path.relative_to(self.source_root).as_posix()
            hasher.update(rel.encode("utf-8"))
            hasher.update(b"\0")
            hasher.update(file_path.read_bytes())
            hasher.update(b"\0")
        return hasher.hexdigest()

    def build(self) -> dict:
        operations: dict[str, dict] = {}
        components: dict[str, dict] = {}
        file_to_entity: dict[str, list[dict]] = {}
        symbol_table: dict[str, dict] = {}

        for file_path in self._iter_source_files():
            rel = file_path.relative_to(self.source_root).as_posix()
            entities: list[dict] = []

            for symbol in self._parse_file(file_path, rel):
                entities.append({"kind": symbol["kind"], "name": symbol["name"]})
                key = f"{symbol['kind']}::{symbol['name']}"
                symbol_table[key] = {
                    "kind": symbol["kind"],
                    "name": symbol["name"],
                    "file": rel,
                    "path": symbol["path"],
                    "attributes": symbol["attributes"],
                }

                if symbol["kind"] == "operation":
                    operations[symbol["name"]] = {
                        "file": rel,
                        "path": symbol["path"],
                        "attributes": symbol["attributes"],
                    }
                elif symbol["kind"] == "component":
                    components[symbol["name"]] = {
                        "file": rel,
                        "path": symbol["path"],
                        "attributes": symbol["attributes"],
                    }

            file_to_entity[rel] = entities

        return {
            "operations_catalog": dict(sorted(operations.items())),
            "component_catalog": dict(sorted(components.items())),
            "file_to_entity_map": dict(sorted(file_to_entity.items())),
            "normalized_symbol_table": dict(sorted(symbol_table.items())),
        }

    def persist(self, out_root: Path) -> Path:
        source_hash = self.source_hash()
        payload = self.build()
        artifact_dir = out_root / source_hash / self.version
        artifact_dir.mkdir(parents=True, exist_ok=True)

        for name, data in payload.items():
            out_file = artifact_dir / f"{name}.json"
            out_file.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        manifest = {
            "source_hash": source_hash,
            "version": self.version,
            "artifacts": sorted([f"{name}.json" for name in payload]),
        }
        (artifact_dir / "manifest.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        return artifact_dir

    def _iter_source_files(self) -> Iterable[Path]:
        files = [
            p
            for p in self.source_root.rglob("*")
            if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS
        ]
        return sorted(files, key=lambda p: p.relative_to(self.source_root).as_posix())

    def _parse_file(self, file_path: Path, rel_path: str) -> list[dict]:
        tree = ET.parse(file_path)
        root = tree.getroot()
        symbols: list[dict] = []

        def walk(node: ET.Element, ancestry: list[str]) -> None:
            tag = self._normalize_tag(node.tag)
            path = "/".join(ancestry + [tag])
            kind = ENTITY_HINTS.get(tag)
            name = (
                node.attrib.get("name")
                or node.attrib.get("id")
                or node.attrib.get("key")
            )
            if kind and name:
                symbols.append(
                    {
                        "kind": kind,
                        "name": name,
                        "file": rel_path,
                        "path": path,
                        "attributes": dict(sorted(node.attrib.items())),
                    }
                )

            for child in list(node):
                walk(child, ancestry + [tag])

        walk(root, [])
        return sorted(symbols, key=lambda s: (s["kind"], s["name"], s["path"]))

    @staticmethod
    def _normalize_tag(tag: str) -> str:
        if "}" in tag:
            tag = tag.split("}", 1)[1]
        return tag.strip().lower()


def build_index(source_root: str | Path, out_root: str | Path, version: str) -> Path:
    indexer = ComposerIndexer(Path(source_root), version)
    return indexer.persist(Path(out_root))
