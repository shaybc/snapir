"""Stage pinned tools and optional demo references alongside assembled operations."""
import json
import os
import subprocess
from pathlib import Path
from runtime.fixture_jdbc_tools.releases import digest, file_hash
from runtime.fixture_jdbc_tools.staging import stage_release
from runtime.fixture_demo.catalogue import prepare_catalogue
from runtime.fixture_demo.artifact_paths import demo_artifact,migrate_demo_artifacts

PINNED_BUNDLE = '5aa3e41aaef03d1a140a433a931cfd1b9813cd638dc4d003ffd950758fccab56'


def prepare_operation_demo(project, output_root, identity, *, bundle_id=PINNED_BUNDLE, port=15432, store=None, generation_issue=None):
    """Prepare external demo settings without modifying code, fixture banks or production settings.

    Missing optional evidence produces an unavailable report. Existing user-owned
    bindings/overlays are preserved and verified on execution, never silently replaced.
    """
    project, output_root = Path(project).resolve(), Path(output_root).resolve()
    result = dict(operation=identity, status='unavailable', issues=[])
    try:migrate_demo_artifacts(project)
    except (ValueError,OSError) as error:return dict(result,issues=[str(error)])
    report_path=demo_artifact(project,'demo-preparation.json')
    previous_report=json.loads(report_path.read_text(encoding='utf-8')) if report_path.exists() else None
    try:
        if generation_issue:raise ValueError(generation_issue)
        if not 1024<=port<=65535:raise ValueError('Demo port must be between 1024 and 65535')
        catalogue, evidence = prepare_catalogue(project, identity)
        binding_path = project/'standalone/operation.json'
        if not binding_path.exists():
            raise ValueError('Standalone operation binding is missing')
        tool = stage_release(bundle_id, output_root/'demo-tools'/bundle_id, store)
        catalogue_path = output_root/'demo'/identity/digest(catalogue)/'catalogue.json'
        catalogue_path.parent.mkdir(parents=True, exist_ok=True)
        if catalogue_path.exists():
            if json.loads(catalogue_path.read_text(encoding='utf-8')) != catalogue:
                raise ValueError('Existing demo catalogue differs; preserve it and select a new explicit revision')
        else:
            catalogue_path.write_text(json.dumps(catalogue, indent=2)+'\n', encoding='utf-8')
        java=str(Path(os.environ['JAVA_HOME'])/'bin/java.exe') if os.name=='nt' and os.environ.get('JAVA_HOME') else 'java'
        command=[java,'-jar',str(Path(tool['root'])/tool['server_jar']),'verify-fixtures',
            '--catalogue',str(catalogue_path),'--expected-hash',digest(catalogue)]
        for root in evidence['fixture_roots']:command.extend(['--fixture-root',root])
        checked=subprocess.run(command,capture_output=True,text=True,timeout=30)
        if checked.returncode:raise ValueError('Prebuilt fixture server rejected the saved catalogue: '+checked.stderr[-1000:])
        result.update(status='prepared', bundle_id=bundle_id, manifest_hash=tool['manifest_hash'],
            catalogue=str(catalogue_path), catalogue_hash=digest(catalogue), **evidence)
        binding = json.loads(binding_path.read_text(encoding='utf-8'))
        scenarios = list(catalogue['scenarios'])
        # Selection is explicit when more than one complete scenario was retained.
        if len(scenarios) != 1 and not evidence['selected_scenario']:
            raise ValueError('Select exactly one operation demo scenario in a dedicated preparation definition')
        scenario = evidence['selected_scenario'] or scenarios[0]
        resources = catalogue['scenarios'][scenario]['resources']
        if len(resources) != 1:
            raise ValueError('The standalone launcher currently supports one configured database; multiple resources are unresolved')
        resource = next(iter(resources))
        relative = lambda p: Path(os.path.relpath(p, binding_path.parent)).as_posix()
        demo = dict(database='demo', jdbc_url=f'jdbc:fixtures://127.0.0.1:{port}/{scenario}?resource={resource}',
            driver_class=tool['driver_class'], tool_root=relative(tool['root']), bundle_id=bundle_id,
            manifest_hash=tool['manifest_hash'], release_hash=file_hash(Path(tool['root'])/'release.json'),
            driver_jar=tool['driver_jar'], server_jar=tool['server_jar'], fixture_catalogue=relative(catalogue_path),
            catalogue_hash=digest(catalogue), fixture_roots=[relative(p) for p in evidence['fixture_roots']],
            startup_timeout_ms=15000, invocation_timeout_ms=120000, stop_when_finished=True)
        demo['operation_files']={p.relative_to(project).as_posix():file_hash(p)
            for p in [project/'pom.xml',*project.joinpath('src/main').rglob('*')] if p.is_file()}
        from runtime.fixture_demo.managed_outputs import set_demo_binding
        set_demo_binding(binding_path,demo)
        from runtime.test_assets.store import load
        from runtime.test_assets.references import resolve
        from models.shared_test_fixture import SharedFixtureBank
        from runtime.fixture_demo.managed_outputs import write_demo_request
        ref=evidence['requests'][scenario]['input_xml']
        _,documents=load(ref['asset_root'],ref['manifest_hash'])
        request_xml=resolve(SharedFixtureBank.model_validate(documents['fixtures.json']),dict(fixture_id=ref['fixture_id'],pointer=ref['pointer']))
        request_path=write_demo_request(project,request_xml)
        if request_path:result['demo_request']=str(request_path)
        else:result['request_notice']='Existing user-edited standalone/demo-request.xml was preserved'
    except (ValueError, OSError, KeyError, subprocess.TimeoutExpired) as error:
        result.update(status='unavailable', issues=[str(error)])
    from runtime.fixture_demo.values import prepare_demo_values
    prepare_demo_values(project, result, previous_report=previous_report)
    report_path.parent.mkdir(parents=True,exist_ok=True)
    report_path.write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8')
    return result
