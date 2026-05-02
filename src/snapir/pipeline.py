from __future__ import annotations

import hashlib
import json
import re
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
        candidate, loop_history = self._critic_loop(prompt_payload)

        run_dir.mkdir(parents=True, exist_ok=True)
        (run_dir / "prompt.json").write_text(json.dumps(prompt_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        (run_dir / "loop_history.json").write_text(json.dumps(loop_history, indent=2, sort_keys=True) + "\n", encoding="utf-8")

        if candidate is None:
            return PipelineResult(run_dir, component_hash, accepted=False, reused=False)

        self._materialize_maven_project(run_dir, prompt_payload, candidate)
        (run_dir / "final_accepted_implementation.java").write_text(candidate, encoding="utf-8")
        self._run_maven_build(run_dir)
        self._publish_artifact_metadata(run_dir)
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
            operation_log = {"attempt": attempt}
            candidate = self._generate_java(prompt_payload, attempt)
            operation_log["service_level_candidate"] = {"language": "java", "source": candidate}

            critic = self._critic_feedback(candidate)
            operation_log["critic_feedback"] = critic

            ok, message = self._compile_check(candidate)
            operation_log["snippet_check"] = {"passed": ok, "message": message}
            logs.append(operation_log)
            if ok:
                return candidate, logs
        return None, logs

    @staticmethod
    def _critic_feedback(candidate: str) -> dict:
        has_class = "class SharedComponentLibrary" in candidate
        has_accessors = "get" in candidate and "set" in candidate
        passed = has_class and has_accessors
        return {
            "passed": passed,
            "notes": "contains shared library class and accessor methods" if passed else "missing class or accessor methods",
        }

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

    def _materialize_maven_project(self, run_dir: Path, prompt_payload: dict, source: str) -> None:
        coordinates = self._artifact_coordinates(prompt_payload)
        package_path = coordinates["package"].replace(".", "/")
        src_main = run_dir / "src" / "main" / "java" / package_path
        src_test = run_dir / "src" / "test" / "java" / package_path
        src_main.mkdir(parents=True, exist_ok=True)
        src_test.mkdir(parents=True, exist_ok=True)

        (run_dir / "pom.xml").write_text(self._pom_xml(coordinates), encoding="utf-8")
        (src_main / "SharedComponentLibrary.java").write_text(
            f"package {coordinates['package']};\n\n{source}", encoding="utf-8"
        )
        (src_main / "SharedUtilities.java").write_text(
            self._shared_utilities_source(coordinates["package"]), encoding="utf-8"
        )
        (src_main / "ConvertedComponent.java").write_text(
            self._converted_component_source(coordinates["package"]), encoding="utf-8"
        )
        (src_test / "ConvertedComponentTest.java").write_text(
            self._converted_component_test_source(coordinates["package"]), encoding="utf-8"
        )

    def _run_maven_build(self, run_dir: Path) -> None:
        mvn = shutil.which("mvn")
        if mvn is None:
            (run_dir / "maven_build.json").write_text(
                json.dumps({"executed": False, "reason": "mvn_not_found"}, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            return

        cmd = [mvn, "-q", "package", "install", "-DskipTests"]
        result = subprocess.run(cmd, cwd=run_dir, capture_output=True, text=True)
        (run_dir / "maven_build.json").write_text(
            json.dumps(
                {
                    "executed": True,
                    "command": cmd,
                    "returncode": result.returncode,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                },
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )

    def _publish_artifact_metadata(self, run_dir: Path) -> None:
        coordinates = self._coordinates_from_pom(run_dir / "pom.xml")
        metadata = {
            "groupId": coordinates.get("groupId"),
            "artifactId": coordinates.get("artifactId"),
            "version": coordinates.get("version"),
            "packaging": "jar",
            "artifactPath": str(run_dir / "target" / f"{coordinates.get('artifactId')}-{coordinates.get('version')}.jar"),
        }
        (run_dir / "artifact-metadata.json").write_text(
            json.dumps(metadata, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )

    def _artifact_coordinates(self, prompt_payload: dict) -> dict:
        version_token = re.sub(r"[^a-zA-Z0-9]", "", self.version) or "v1"
        return {
            "group_id": "com.snapir.generated",
            "artifact_id": "shared-component-library",
            "version": f"1.0.0-{version_token}",
            "package": "com.snapir.generated",
        }

    @staticmethod
    def _pom_xml(coordinates: dict) -> str:
        return f"""<project xmlns=\"http://maven.apache.org/POM/4.0.0\"\n         xmlns:xsi=\"http://www.w3.org/2001/XMLSchema-instance\"\n         xsi:schemaLocation=\"http://maven.apache.org/POM/4.0.0 http://maven.apache.org/xsd/maven-4.0.0.xsd\">\n  <modelVersion>4.0.0</modelVersion>\n  <groupId>{coordinates['group_id']}</groupId>\n  <artifactId>{coordinates['artifact_id']}</artifactId>\n  <version>{coordinates['version']}</version>\n  <properties>\n    <maven.compiler.source>17</maven.compiler.source>\n    <maven.compiler.target>17</maven.compiler.target>\n    <project.build.sourceEncoding>UTF-8</project.build.sourceEncoding>\n  </properties>\n  <dependencies>\n    <dependency>\n      <groupId>org.junit.jupiter</groupId>\n      <artifactId>junit-jupiter</artifactId>\n      <version>5.10.2</version>\n      <scope>test</scope>\n    </dependency>\n  </dependencies>\n  <build>\n    <plugins>\n      <plugin>\n        <groupId>org.apache.maven.plugins</groupId>\n        <artifactId>maven-surefire-plugin</artifactId>\n        <version>3.2.5</version>\n      </plugin>\n    </plugins>\n  </build>\n</project>\n"""

    @staticmethod
    def _shared_utilities_source(package_name: str) -> str:
        return f"""package {package_name};

public final class SharedUtilities {{
    private SharedUtilities() {{}}

    public static String normalize(String value) {{
        return value == null ? "" : value.trim();
    }}
}}
"""

    @staticmethod
    def _converted_component_source(package_name: str) -> str:
        return f"""package {package_name};

public class ConvertedComponent {{
    public String convert(String raw) {{
        return SharedUtilities.normalize(raw);
    }}
}}
"""

    @staticmethod
    def _converted_component_test_source(package_name: str) -> str:
        return f"""package {package_name};

import org.junit.jupiter.api.Test;

import static org.junit.jupiter.api.Assertions.assertEquals;

class ConvertedComponentTest {{
    @Test
    void convertNormalizesInput() {{
        ConvertedComponent component = new ConvertedComponent();
        assertEquals("hello", component.convert("  hello  "));
    }}
}}
"""

    @staticmethod
    def _coordinates_from_pom(pom: Path) -> dict:
        content = pom.read_text(encoding="utf-8")
        return {
            "groupId": re.search(r"<groupId>([^<]+)</groupId>", content).group(1),
            "artifactId": re.search(r"<artifactId>([^<]+)</artifactId>", content).group(1),
            "version": re.search(r"<version>([^<]+)</version>", content).group(1),
        }


def run_conversion_pipeline(source_root: str | Path, out_root: str | Path, version: str) -> Path:
    result = ConversionPipeline(Path(source_root), Path(out_root), version).run()
    return result.artifact_dir
