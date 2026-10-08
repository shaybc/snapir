"""Run Bank Demo inventory and closure in a disposable workspace, without model calls."""

from runtime.workspace_paths import run_report_path, write_run_report
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime.project_paths import project_root

from runtime.configuration import load_configuration
from runtime.pipeline_runner import run_pipeline
from runtime.checkpoints import resume_pipeline


def main():
    """Report actual closure blockers and verify the three repaired integration gaps."""
    profile = load_configuration(project_root() / "configs/bank_demo.yaml")
    profile.model_provider = "mock"
    profile.gate_policies["1"] = "automatic"
    profile.maven_settings_path = None
    with tempfile.TemporaryDirectory(prefix="snapir-closure-smoke-") as temporary:
        profile.output_root = temporary
        directory = run_pipeline(profile, "closure-smoke")
        inventory = json.loads((directory / "reports" / "component_inventory.json").read_text(encoding="utf-8"))
        usage = json.loads((directory / "reports" / "component_usage.json").read_text(encoding="utf-8"))
        print("Workspace Java implementations:", len(inventory["implementations"]))
        print("Configured definitions:", len(inventory["definitions"]))
        print("Configured operation uses:", len(inventory["uses"]))
        print("Implementations used by multiple operations:", sum(item["operation_count"] > 1 for item in usage))
        resume_pipeline(temporary, "closure-smoke")
        closures = json.loads(run_report_path(directory, "dependency_closure.json").read_text(encoding="utf-8"))
        for closure in closures:
            print(closure["operation_id"], closure["status"])
            for issue in closure["blocking_issues"]:
                print(" -", issue["entity_id"], issue["detail"])
        repaired = bool(closures) and all(
            "StandardErrorRSFmt" in closure["formats"]["all_format_ids"] and
            not any(issue["kind"] in {"BLOCKED_MISSING_FORMAT", "BLOCKED_UNKNOWN_TAG"} or
                    issue["detail"] == "opStep without JavaClassRef" for issue in closure["blocking_issues"])
            for closure in closures)
        print("Repaired integration checks:", "passed" if repaired else "failed")
        return 0 if repaired else 1


if __name__ == "__main__":
    raise SystemExit(main())
