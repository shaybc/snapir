"""Prepare complete, cached original-code packages independently of conversion state."""
import json,os,shutil,tempfile,subprocess
from pathlib import Path
from models.composer_unit_result import ComposerUnitResult
from models.composer_unit_manifest import ComposerUnitManifest
from models.native_unit_bundle import NativeSourceFile
from runtime.composer_units.discovery import discover
from runtime.composer_units.framework_binding import resolve,preflight
from runtime.composer_units.cache import verify,file_hash
from runtime.java_toolchain import java_scope,java_environment
from tools.behavior_verification.boundary_contracts import boundary_contract,digest
from tools.behavior_verification.boundary_execution import compile_boundary_side
from tools.behavior_verification.java_tool import default_tool_path


def prepare(spec,profile,directory,*,tool=None):
    """Discover from the configured workspace; compile originals, never generated replacements."""
    try:
        with java_scope(profile):
            unit,discovery=discover(spec,profile);binding=resolve(spec,unit)
            harness=Path(tool or default_tool_path()).resolve()
            originals=discovery['originals'];originals[str(harness)]=file_hash(harness)
            originals.update({str(path.resolve()):file_hash(path) for path in Path(__file__).parent.glob('*.py')})
            home=(java_environment(profile.java_version,profile.java_home) or os.environ).get('JAVA_HOME')
            if home and (Path(home)/'release').exists():originals[str(Path(home)/'release')]=file_hash(Path(home)/'release')
            identity=digest(dict(spec=spec.model_dump(mode='json'),unit=unit,originals=originals,java=profile.java_version,
                runner={p.name:file_hash(p) for p in Path(__file__).parent.glob('*.py')}))
            root=Path(directory).resolve()/identity
            if root.exists():verify(root);return ComposerUnitResult(status='package_ready',package=str(root))
            root.parent.mkdir(parents=True,exist_ok=True);temporary=Path(tempfile.mkdtemp(prefix='.composer-unit-',dir=root.parent))
            try:
                shutil.copy2(harness,temporary/'harness.jar');binding.classpath=[]
                for jar in discovery['libraries']:
                    target=temporary/'libraries'/(file_hash(jar)[:16]+'-'+Path(jar).name);target.parent.mkdir(exist_ok=True)
                    shutil.copy2(jar,target);binding.classpath.append(str(target))
                from runtime.test_assets.runtime_dependencies import verify_runtime_dependencies
                verify_runtime_dependencies(temporary/'harness.jar',binding.classpath)
                boundary=boundary_contract(unit)
                compiled=compile_boundary_side(unit,boundary,binding,temporary/'runtime','original',temporary/'harness.jar',fixture_resources=True,allow_unknown_calls=True)
                preflight(spec,unit,binding,compiled,temporary/'preflight.xml')
                for source in unit['sources']:
                    target=temporary/'sources'/Path(source['original_path']).relative_to(Path(profile.source_root).resolve())
                    target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source['original_path'],target)
                def relative(path):return Path(path).relative_to(temporary).as_posix()
                receipt=dict(directory=relative(compiled['directory']),classes=relative(compiled['classes']),classpath=[relative(p) for p in compiled['classpath']],
                    hashes={('dependency:'+relative(k[11:])) if k.startswith('dependency:') else k:v for k,v in compiled['hashes'].items()})
                serialized=binding.model_dump(mode='json');serialized['classpath']=[relative(p) for p in binding.classpath]
                for name,data in [('specification.json',spec.model_dump(mode='json')),('unit.json',unit),('binding.json',serialized),('compiled.json',receipt),('discovery-report.json',discovery),('build-report.json',dict(compilation='passed',framework_preflight='passed',business_execution='not_run'))]:
                    (temporary/name).write_text(json.dumps(data,indent=2),encoding='utf-8')
                manifest=ComposerUnitManifest(identity=identity,originals=originals,files={p.relative_to(temporary).as_posix():file_hash(p) for p in temporary.rglob('*') if p.is_file()})
                (temporary/'manifest.json').write_text(manifest.model_dump_json(indent=2),encoding='utf-8');verify(temporary)
                try:os.rename(temporary,root)
                except FileExistsError:verify(root)
                verify(root)
            finally:
                if temporary.exists() and temporary.resolve().parent==root.parent:shutil.rmtree(temporary)
            return ComposerUnitResult(status='package_ready',package=str(root))
    except (ValueError,OSError,RuntimeError,subprocess.TimeoutExpired) as error:return ComposerUnitResult(status='preparation_unavailable',issues=[str(error)])
