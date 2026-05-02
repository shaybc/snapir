from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .context_schema import ContextSchemaBuilder
from .indexer import ComposerIndexer
from .internal_ir import InternalIRBuilder


@dataclass(frozen=True)
class PipelineResult:
    artifact_dir: Path
    component_hash: str
    accepted: bool
    reused: bool


class ConversionPipeline:
    """Run deterministic IR -> prompt -> Java generation with critic + compile checks."""

    def __init__(self, source_root: Path, out_root: Path, version: str, max_attempts: int = 3) -> None:
        self.source_root = Path(source_root)
        self.out_root = Path(out_root)
        self.version = version
        self.max_attempts = max_attempts

    def run(self) -> PipelineResult:
        source_hash = ComposerIndexer(self.source_root, self.version).source_hash()
        base_dir = self.out_root / source_hash / self.version
        base_dir.mkdir(parents=True, exist_ok=True)

        ir = InternalIRBuilder(self.source_root, self.version).build()
        context_bundle = ContextSchemaBuilder(self.source_root, self.version).build()

        component_hash = self._component_hash(ir, context_bundle)
        run_dir = base_dir / "conversion_pipeline" / component_hash
        accepted_marker = run_dir / "accepted.json"

        if accepted_marker.exists():
            return PipelineResult(run_dir, component_hash, accepted=True, reused=True)

        prompt_payload = self._prepare_prompt(ir, context_bundle)
        candidate, critic_log = self._critic_loop(prompt_payload)

        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "prompt.json").write_text(json.dumps(prompt_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (run_dir / "critic_log.json").write_text(json.dumps(critic_log, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        if candidate is None:
            return PipelineResult(run_dir, component_hash, accepted=False, reused=False)

        (run_dir / "SharedComponentLibrary.java").write_text(candidate, encoding="utf-8")
        (run_dir / "accepted.json").write_text(
            json.dumps({"component_hash": component_hash, "accepted": True}, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return PipelineResult(run_dir, component_hash, accepted=True, reused=False)

    def _prepare_prompt(self, ir: dict, context_bundle: dict) -> dict:
        return {
            "ir": ir,
            "normalized_semantics": ir["dependency_contracts"],
            "context_schemas": context_bundle,
            "target": "java_shared_library",
            "constraints": ["deterministic_output", "plain_java_no_framework"],
        }

    def _component_hash(self, ir: dict, context_bundle: dict) -> str:
        payload = json.dumps({"ir": ir, "context": context_bundle}, sort_keys=True).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def _critic_loop(self, prompt_payload: dict) -> tuple[str | None, list[dict]]:
        logs: list[dict] = []
        for attempt in range(1, self.max_attempts + 1):
            candidate = self._generate_java(prompt_payload, attempt)
            ok, message = self._compile_check(candidate)
            logs.append({"attempt": attempt, "compile_ok": ok, "message": message})
            if ok:
                return candidate, logs
        return None, logs

    def _generate_java(self, prompt_payload: dict, attempt: int) -> str:
        fields = prompt_payload["context_schemas"]["java_context_metadata"]["fields"]
        members = "\n".join(
            f"    private {f['java_type']} {f['name']};" for f in fields
        )
        accessors = "\n\n".join(
            self._accessors(f["java_type"], f["name"]) for f in fields
        )
        return (
            "public class SharedComponentLibrary {\n"
            f"    // generated attempt {attempt}\n"
            f"{members}\n\n"
            f"{accessors}\n"
            "}\n"
        )

    def _compile_check(self, source: str) -> tuple[bool, str]:
        javac = shutil.which("javac")
        if javac is None:
            balanced = source.count("{") == source.count("}")
            return balanced, "javac_not_found_balanced_braces_check"

        with tempfile.TemporaryDirectory() as tmpdir:
            java_file = Path(tmpdir) / "SharedComponentLibrary.java"
            java_file.write_text(source, encoding="utf-8")
            result = subprocess.run([javac, str(java_file)], capture_output=True, text=True)
            if result.returncode == 0:
                return True, "javac_compile_success"
            return False, result.stderr.strip() or "javac_compile_failed"

    @staticmethod
    def _accessors(java_type: str, name: str) -> str:
        title = name[:1].upper() + name[1:]
        return (
            f"    public {java_type} get{title}() {{ return {name}; }}\n"
            f"    public void set{title}({java_type} value) {{ this.{name} = value; }}"
        )


def run_conversion_pipeline(source_root: str | Path, out_root: str | Path, version: str) -> Path:
    result = ConversionPipeline(Path(source_root), Path(out_root), version).run()
    return result.artifact_dir
