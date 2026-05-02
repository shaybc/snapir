from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable
import xml.etree.ElementTree as ET

from .classifier import DataflowClassifier
from .indexer import ComposerIndexer, SUPPORTED_EXTENSIONS

TYPE_ATTRIBUTE_PRECEDENCE = (
    "javaType",
    "type",
    "dataType",
    "datatype",
    "format",
    "class",
)

DEFAULT_CLASS_TO_LOGICAL_TYPE = {
    "INPUT": "string",
    "INTERMEDIATE": "string",
    "ERROR": "error_code",
    "OUTPUT": "string",
}


class ContextSchemaBuilder:
    """Generate deterministic context schemas and Java metadata from classification outputs."""

    def __init__(self, source_root: Path, version: str) -> None:
        self.source_root = Path(source_root)
        self.version = version

    def build(self) -> dict[str, dict]:
        classification = DataflowClassifier(self.source_root, self.version).build()
        field_classification: dict[str, str] = classification["field_classification"]
        traces = classification["classification_traces"]
        format_attrs = self._collect_format_field_attributes()

        field_records = []
        for field_name in sorted(field_classification):
            category = field_classification[field_name]
            attrs = format_attrs.get(field_name, {})
            resolved_type, rule = self._resolve_type(field_name, category, attrs)
            java_name = self._to_java_field_name(field_name)
            field_records.append(
                {
                    "name": field_name,
                    "classification": category,
                    "logical_type": resolved_type,
                    "type_resolution_rule": rule,
                    "required": category in {"INPUT", "OUTPUT"},
                }
            )

        trace_index = {t["field"]: t for t in traces}
        java_fields = []
        for record in field_records:
            field_name = record["name"]
            category = record["classification"]
            java_type = self._logical_to_java_type(record["logical_type"])
            java_fields.append(
                {
                    "name": self._to_java_field_name(field_name),
                    "source_name": field_name,
                    "java_type": java_type,
                    "comment": f"{category} context field derived from classifier rule '{trace_index[field_name]['rule']}'.",
                    "annotation_hints": self._annotation_hints(category, java_type),
                }
            )

        return {
            "context_schema": {
                "schema_version": "1",
                "fields": field_records,
            },
            "java_context_metadata": {
                "schema_version": "1",
                "field_ordering": [f["name"] for f in java_fields],
                "fields": java_fields,
            },
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

    def _collect_format_field_attributes(self) -> dict[str, dict[str, str]]:
        fields: dict[str, dict[str, str]] = {}
        for file_path in self._iter_source_files():
            root = ET.parse(file_path).getroot()
            self._walk_field_attrs(root, fields)
        return fields

    def _walk_field_attrs(self, node: ET.Element, fields: dict[str, dict[str, str]]) -> None:
        tag = self._normalize_tag(node.tag)
        if tag in {"field", "attribute", "element", "member"}:
            name = node.attrib.get("name") or node.attrib.get("id") or node.attrib.get("key")
            if name and name not in fields:
                fields[name] = dict(node.attrib)
        for child in list(node):
            self._walk_field_attrs(child, fields)

    def _resolve_type(self, field_name: str, category: str, attrs: dict[str, str]) -> tuple[str, str]:
        for key in TYPE_ATTRIBUTE_PRECEDENCE:
            if key in attrs and attrs[key].strip():
                return self._normalize_declared_type(attrs[key]), f"attribute_precedence:{key}"
        return self._infer_name_type(field_name, category), "inferred_from_name_and_class"

    @staticmethod
    def _normalize_declared_type(raw: str) -> str:
        value = raw.strip().lower()
        aliases = {
            "integer": "int",
            "long": "long",
            "double": "double",
            "float": "float",
            "decimal": "decimal",
            "bool": "boolean",
            "boolean": "boolean",
            "date": "date",
            "datetime": "datetime",
            "timestamp": "datetime",
            "string": "string",
            "uuid": "uuid",
        }
        return aliases.get(value, value)

    def _infer_name_type(self, field_name: str, category: str) -> str:
        lowered = field_name.lower()
        if any(tok in lowered for tok in ("date", "time", "timestamp")):
            return "datetime"
        if any(tok in lowered for tok in ("count", "total", "qty", "amount", "number", "num")):
            return "int"
        if "id" in lowered or lowered.endswith("key"):
            return "string"
        return DEFAULT_CLASS_TO_LOGICAL_TYPE.get(category, "string")

    @staticmethod
    def _logical_to_java_type(logical: str) -> str:
        mapping = {
            "int": "Integer",
            "long": "Long",
            "double": "Double",
            "float": "Float",
            "decimal": "java.math.BigDecimal",
            "boolean": "Boolean",
            "date": "java.time.LocalDate",
            "datetime": "java.time.OffsetDateTime",
            "uuid": "java.util.UUID",
            "error_code": "String",
            "string": "String",
        }
        return mapping.get(logical, "String")

    @staticmethod
    def _annotation_hints(category: str, java_type: str) -> list[str]:
        hints: list[str] = ["@JsonProperty"]
        if category in {"INPUT", "OUTPUT"}:
            hints.append("@NotNull")
        if java_type == "String" and category == "ERROR":
            hints.append("@Pattern")
        return hints

    @staticmethod
    def _to_java_field_name(name: str) -> str:
        parts = [p for p in name.replace("-", "_").split("_") if p]
        if len(parts) > 1:
            return parts[0].lower() + "".join(p[:1].upper() + p[1:] for p in parts[1:])
        return name[:1].lower() + name[1:]

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


def build_context_schema(source_root: str | Path, out_root: str | Path, version: str) -> Path:
    return ContextSchemaBuilder(Path(source_root), version).persist(Path(out_root))
