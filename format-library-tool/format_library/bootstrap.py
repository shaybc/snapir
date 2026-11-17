"""Validate/install Python dependencies before importing dependency-dependent tool modules."""
import argparse
import importlib.metadata
from pathlib import Path
import subprocess
import sys

TOOL_ROOT = Path(__file__).resolve().parents[1]


def unmet_requirements(path):
    """Check direct and active transitive requirements locally, without contacting an index."""
    from pip._vendor.packaging.requirements import Requirement
    pending = [(Requirement(line.strip()), ('',)) for line in Path(path).read_text(encoding='utf-8').splitlines()
               if line.strip() and not line.lstrip().startswith('#')]
    missing, seen = set(), set()
    while pending:
        requirement, parent_extras = pending.pop()
        if requirement.marker and not any(requirement.marker.evaluate({'extra': extra}) for extra in parent_extras):
            continue
        try:
            distribution = importlib.metadata.distribution(requirement.name)
        except importlib.metadata.PackageNotFoundError:
            missing.add(str(requirement))
            continue
        if not requirement.specifier.contains(distribution.version, prereleases=True):
            missing.add(str(requirement))
        key = (requirement.name.lower().replace('_', '-'), tuple(sorted(requirement.extras)))
        if key in seen:
            continue
        seen.add(key)
        extras = ('', *sorted(requirement.extras))
        pending.extend((Requirement(value), extras) for value in distribution.requires or [])
    return sorted(missing)


def ensure_python():
    """Install only when requirements are unmet; never request upgrades of satisfied packages."""
    print('Checking Python requirements...', flush=True)
    try:
        import pip  # noqa: F401 -- needed for its bundled requirement parser and installer
    except ImportError:
        subprocess.run([sys.executable, '-m', 'ensurepip'], check=True)
    requirements = TOOL_ROOT / 'requirements.txt'
    missing = unmet_requirements(requirements)
    if not missing:
        print('Python requirements ready; no installation needed.', flush=True)
        return
    print('Installing missing/incompatible Python requirements: ' + ', '.join(missing), flush=True)
    subprocess.run([sys.executable, '-m', 'pip', 'install', '--disable-pip-version-check',
                    '-r', str(requirements)], check=True)
    importlib.invalidate_caches()
    missing = unmet_requirements(requirements)
    if missing:
        raise ValueError('Python requirements remain unsatisfied: ' + ', '.join(missing))
    print('Python requirements ready.', flush=True)


def main(argv=None):
    """Prepare tool dependencies using the same configuration and interpreter as the launcher."""
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument('--config', default=str(TOOL_ROOT / 'config.yaml'))
    args, _ = parser.parse_known_args(argv)
    try:
        ensure_python()
        from format_library.configuration import load_config
        from format_library.java_prerequisites import ensure_scanner
        ensure_scanner(load_config(args.config))
        return 0
    except (ValueError, OSError, subprocess.SubprocessError, ImportError) as error:
        print('Dependency setup: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
