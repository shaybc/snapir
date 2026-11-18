"""Standalone launcher; install only this tool's missing Python requirements."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

if importlib.util.find_spec('yaml') is None:
    result=subprocess.run([sys.executable,'-m','pip','install','-r',str(Path(__file__).parent/'requirements.txt')],
                          stdout=sys.stderr,stderr=sys.stderr)
    if result.returncode:
        print(json.dumps(dict(schema_version='java-behavior-comparison-v1',decision='error',complete=False,
                              evidence_level='static_analysis',error='Comparator requirement installation failed; see stderr')))
        raise SystemExit(3)
from comparator.__main__ import main
raise SystemExit(main())
