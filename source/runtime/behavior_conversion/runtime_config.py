"""Create shared external-system settings beside generated native operations."""

import json
from pathlib import Path


def ensure_runtime_config(output_root):
    """Create an empty runtime configuration once, preserving user settings on resume."""
    root = Path(output_root)
    root.mkdir(parents=True, exist_ok=True)
    path = root / "runtime-config.json"
    template = {"databases": {"default": {
        "ip": "", "port": None, "schema": "", "user": "", "password": "",
        "jdbc_url": "", "driver_class": ""
    }}}
    try:
        with path.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(template, indent=2) + "\n")
    except FileExistsError:
        pass
    return path
