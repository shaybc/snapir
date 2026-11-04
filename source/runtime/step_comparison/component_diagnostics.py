"""Optional whole-step scenario diagnostics after native build/JUnit validation."""
import json
from pathlib import Path
from models.native_unit_bundle import NativeSourceFile
from runtime.test_assets.preparation import current,enabled
from runtime.test_assets.materialization import comparison_plan
from runtime.step_comparison.runner import run_step_comparison


def diagnose_step(validator,files,directory,native_classpath):
    """Never change conversion acceptance, production or retry counters from a diagnostic."""
    if not enabled(validator.profile) or not validator.profile.format_comparison.enabled:return
    root=Path(directory);root.mkdir(parents=True,exist_ok=True)
    try:
        assets=current()
        if assets is None:raise ValueError('Shared step comparison scenarios are unavailable')
        configured=validator.request['configured_unit'];unit=validator.units[configured['unit_id']]
        sources=[NativeSourceFile(path=p,content=t) for p,t in files.items() if p.startswith('src/main/java/')]
        plan=comparison_plan(configured.get('logical_id',configured['unit_id']),unit,sources,assets['bank'],assets['comparisons'],assets['manifest_hash'])
        plan.original_step_implementation=configured['resolved_implementation']
        plan.native_classpath=list(native_classpath);plan.original_framework.classpath=list(validator.profile.classpath_jars)
        return run_step_comparison(plan,validator.profile,root/'execution')
    except Exception as error:
        result=dict(status='comparison_unavailable',reason=str(error),acceptance_changed=False)
        (root/'unavailable.json').write_text(json.dumps(result,indent=2),encoding='utf-8');return result
