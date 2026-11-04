"""Execute retained AI comparison scenarios independently of the JUnit generation outcome."""
import argparse
import json
from pathlib import Path
from models.shared_test_fixture import SharedFixtureBank
from models.comparison_test_scenario import ComparisonScenarioSuite
from models.native_unit_bundle import NativeSourceFile
from runtime.configuration import load_configuration
from runtime.java_toolchain import java_scope
from runtime.managed_projects import create_build_context
from runtime.behavior_conversion.verification_classpath import native_runtime_classpath
from runtime.test_assets.store import load
from runtime.test_assets.materialization import comparison_plan
from runtime.format_comparison.runner import run_comparison
from runtime.step_comparison.runner import run_step_comparison
from tools.behavior_verification.experimental_checkpoint import file_hash


def run(profile_path,artifact_root,unit_path,pilot_path,output):
    """No AI calls, test corrections, counter resets or conversion-state writes."""
    profile=load_configuration(profile_path);root=Path(artifact_root).resolve();directory=Path(output).resolve()
    previous=json.loads(Path(pilot_path).read_text(encoding='utf-8'))
    if directory.exists():raise ValueError('Comparison output must be new')
    if any(file_hash(p)!=h for p,h in previous['saved_java_hashes'].items()):raise ValueError('Saved Java changed')
    _,documents=load(previous['asset_root'],previous['fixture_manifest_hash'])
    bank=SharedFixtureBank.model_validate(documents['fixtures.json'])
    suite=ComparisonScenarioSuite.model_validate(documents['comparison-scenarios.json'])
    unit=json.loads(Path(unit_path).read_text(encoding='utf-8'))
    from tools.behavior_verification.boundary_contracts import boundary_contract
    boundary=boundary_contract(unit)
    if any(previous['source_boundary'][key]!=getattr(boundary,key) for key in ['source_manifest_hash','configuration_hash']):
        raise ValueError('Retained comparison source/configuration changed')
    sources=[NativeSourceFile(path=p.relative_to(root).as_posix(),content=p.read_bytes().decode('utf-8')) for p in sorted((root/'src/main/java').rglob('*.java'))]
    plan=comparison_plan(unit.get('logical_id','saved-component'),unit,sources,bank,suite,previous['fixture_manifest_hash'])
    with java_scope(profile):
        context=create_build_context(profile,directory/'runtime-classpath','comparison-classpath')
        plan.native_classpath=native_runtime_classpath(root,context)
        plan.original_framework.classpath=list(profile.classpath_jars)
        if unit['kind']!='configured_step':
            from runtime.composer_units.comparison import prepare_comparison
            plan=prepare_comparison(plan,profile,directory/'original-packages')
        execute=run_step_comparison if unit['kind']=='configured_step' else run_comparison
        result=execute(plan,profile,directory/'execution')
    result['saved_java_unchanged']=all(file_hash(p)==h for p,h in previous['saved_java_hashes'].items())
    (directory/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ['profile','artifact-root','unit','pilot','output']:parser.add_argument('--'+name,required=True)
    args=parser.parse_args();result=run(args.profile,args.artifact_root,args.unit,args.pilot,args.output)
    print(json.dumps(dict(status=result['status'],counts=result['counts'],saved_java_unchanged=result['saved_java_unchanged'])))
