"""Install portable-packaging entry points beside fresh or reused assembled operations."""
from pathlib import Path
from runtime.operation_layout import operation_repository


def write_standalone_packaging(project):
    """Create packaging tools and default Git exclusions without replacing user Git rules."""
    project = Path(project)
    templates = Path(__file__).resolve().parents[2] / 'templates/native_operations/standalone'
    project.mkdir(parents=True, exist_ok=True)
    repository = operation_repository(project)
    repository.mkdir(parents=True, exist_ok=True)
    (repository / 'package-standalone-operation.bat').write_bytes((templates / 'package-standalone-operation.bat').read_bytes())
    packaging = project / 'standalone/packaging'
    packaging.mkdir(parents=True, exist_ok=True)
    # Remove only obsolete converter-owned binary-distribution templates.
    for name in ('StandalonePackageBuild.java', 'build-and-run-operation.bat', 'run-operation.bat', 'README.md'):
        obsolete = packaging / name
        if obsolete.is_file():
            obsolete.unlink()
    for template in (templates / 'packaging').iterdir():
        (packaging / template.name).write_bytes(template.read_bytes())
    ignore = repository / '.gitignore'
    default_ignore = (templates / 'operation.gitignore').read_text(encoding='utf-8')
    if not ignore.exists() or ignore.read_text(encoding='utf-8') == default_ignore.replace('**/target/\n', ''):
        ignore.write_bytes((templates / 'operation.gitignore').read_bytes())
    from runtime.behavior_conversion.standalone_test_support import write_standalone_test_support
    write_standalone_test_support(project)
