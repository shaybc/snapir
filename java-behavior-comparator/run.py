"""Standalone launcher; install only this tool's missing Python requirements."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

def requirements_missing():
    """Install this tool's provider adapters only if they are not already available."""
    for name in ('yaml', 'litellm', 'google.genai'):
        try:
            if importlib.util.find_spec(name) is None:
                return True
        except ModuleNotFoundError:
            return True
    return False


if requirements_missing():
    result=subprocess.run([sys.executable,'-m','pip','install','-r',str(Path(__file__).parent/'requirements.txt')],
                          stdout=sys.stderr,stderr=sys.stderr)
    if result.returncode:
        print(json.dumps(dict(schema_version='java-behavior-comparison-v1',decision='error',complete=False,
                              evidence_level='static_analysis',error='Comparator requirement installation failed; see stderr')))
        raise SystemExit(3)
from comparator.__main__ import main
raise SystemExit(main())
