"""Package a standalone launcher beside each assembled native operation."""

import json
import os
from pathlib import Path

from runtime.behavior_conversion.runtime_config import ensure_runtime_config


def write_standalone_runner(project, output_root, contract):
    """Write launcher assets without editing operation sources or its managed POM."""
    project, output_root = Path(project), Path(output_root)
    configuration = ensure_runtime_config(output_root)
    templates = Path(__file__).resolve().parents[2] / "templates/native_operations/standalone"
    destination = project / "standalone"
    destination.mkdir(parents=True, exist_ok=True)
    for name in ("StandaloneOperationRunner.java", "RuntimeDatabase.java", "README.md"):
        (destination / name).write_bytes((templates / name).read_bytes())
    (project / "run-operation.bat").write_bytes((templates / "run-operation.bat").read_bytes())
    binding = {"service_class": contract.service_api.type_name,
               "runtime_config": Path(os.path.relpath(configuration, destination)).as_posix(),
               "database": "default"}
    (destination / "operation.json").write_text(json.dumps(binding, indent=2) + "\n", encoding="utf-8")
