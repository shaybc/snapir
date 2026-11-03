"""Compile production-only stage artifacts without publishing or granting acceptance."""
from pathlib import Path
from tempfile import TemporaryDirectory
from models.native_unit_bundle import NativeUnitBundle
from models.maven_dependency import MavenDependency
from runtime.behavior_conversion.bundle_output import validate_bundle,accept_bundle
from runtime.behavior_conversion.verification_feedback import VerificationIncomplete


def production_compiler(profile,factory=None,*,prerequisites=None,dependencies=(),project=None):
    """Build a compile adapter using frozen prerequisites; never use previous tests as proof."""
    if factory is None:
        from runtime.managed_projects import create_build_context
        factory=create_build_context
    def compile_only(bundle):
        files=validate_bundle(NativeUnitBundle(files=bundle.files),allowed_classes=profile.allowed_ibm_classes)
        if any(not path.startswith('src/main/java/') for path in files):raise ValueError('Implementation stage accepts production files only')
        frozen=dict(prerequisites or {})
        if project and (Path(project)/'src/main/java').is_dir():
            frozen.update({p.relative_to(project).as_posix():p.read_text(encoding='utf-8') for p in (Path(project)/'src/main/java').rglob('*.java')})
        # Existing project files are compile inputs only; final publication still enforces ownership.
        frozen={path:text for path,text in frozen.items() if path not in files and path.startswith('src/main/java/')}
        pins={}
        from runtime.dependency_policy import canonical_dependencies
        inherited=canonical_dependencies(profile,dependencies,historical=True)
        for value in [*inherited,*canonical_dependencies(profile,bundle.dependencies)]:
            pin=value if isinstance(value,MavenDependency) else MavenDependency.model_validate(value)
            key=(pin.group_id,pin.artifact_id)
            if key in pins and (pins[key].version,pins[key].scope)!=(pin.version,pin.scope):raise ValueError('Compile stage changed a pinned dependency')
            pins[key]=pin
        with TemporaryDirectory(prefix='snapir-stage-compile-') as folder:
            validation,_=accept_bundle(Path(folder)/'native',files,factory,profile,list(pins.values()),
                                      dependency_files=frozen.items(),require_tests=False)
        if not validation.get('build_passed'):raise VerificationIncomplete(dict(stage='compile',issues=['Production compilation did not pass']))
        return validation
    return compile_only
