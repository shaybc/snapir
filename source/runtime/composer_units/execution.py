"""Execute one supplied scenario against an immutable original-code package."""
import json,os
from pathlib import Path
from models.boundary_case import BoundaryCase
from models.boundary_harness_binding import BoundaryHarnessBinding
from models.composer_unit_result import ComposerUnitResult
from runtime.composer_units.cache import verify
from runtime.java_toolchain import java_scope
from tools.behavior_verification.boundary_contracts import boundary_contract
from tools.behavior_verification.boundary_execution import execute_boundary_case,verify_compiled_artifacts


def execute(package,scenario,profile,directory):
    """Fresh JVM/state per execution; observations never write into the cached package."""
    root=Path(package).resolve();output=Path(directory).resolve()
    created=False
    try:
        if output==root or root in output.parents:raise ValueError('Execution output must be separate from immutable package')
        if output.exists():raise ValueError('Execution output must be new')
        verify(root)
        unit=json.loads((root/'unit.json').read_text());binding=BoundaryHarnessBinding.model_validate_json((root/'binding.json').read_text())
        binding.classpath=[str(root/p) for p in binding.classpath]
        compiled=json.loads((root/'compiled.json').read_text());compiled['classes']=root/compiled['classes']
        compiled['classpath']=[str(root/p) for p in compiled['classpath']]
        compiled['hashes']={('dependency:'+str(root/k[11:])) if k.startswith('dependency:') else k:v for k,v in compiled['hashes'].items()}
        output.mkdir(parents=True);created=True;compiled['directory']=output
        case=scenario if isinstance(scenario,BoundaryCase) else BoundaryCase.model_validate(scenario)
        from runtime.test_assets.limits import validate_case_limits
        validate_case_limits([case],profile)
        if binding.original_action and case.decorator_value is not None and not isinstance(case.decorator_value,str):
            raise ValueError('The supported original decorator interface requires a String value or null')
        if not case.case_id or not all(c.isalnum() or c in '_-' for c in case.case_id):raise ValueError('Unsafe case identity')
        with java_scope(profile):
            verify_compiled_artifacts(compiled)
            observation=execute_boundary_case(compiled,unit,boundary_contract(unit),binding,case,timeout=profile.format_comparison.case_timeout_seconds)
            if observation.status=='completed' and observation.invocation_completed is not True:
                observation.status='verification_incomplete';observation.issues.append('Original entry was not invoked; setup did not complete')
            verify_compiled_artifacts(compiled)
        verify(root)
        job=output/'cases'/case.case_id
        (output/'java-command.json').write_text(json.dumps(['java','-ea','-cp',os.pathsep.join(compiled['classpath']),
            'il.co.dcd.verification.harness.BoundaryHarness',str(job/'job.xml'),str(job/'observation.xml')],indent=2))
        result=ComposerUnitResult(status='execution_completed' if observation.status=='completed' else 'execution_unavailable',
            package=str(root),issues=observation.issues,observation=observation.model_dump(mode='json'))
    except (ValueError,OSError,RuntimeError) as error:result=ComposerUnitResult(status='execution_unavailable',package=str(root),issues=[str(error)])
    if created:(output/'result.json').write_text(result.model_dump_json(indent=2),encoding='utf-8')
    return result
