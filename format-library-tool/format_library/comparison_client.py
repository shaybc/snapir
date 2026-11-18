"""CLI/JSON adapter to the independent behavior comparator; no comparator code is imported."""
import json
import os
from pathlib import Path
import subprocess
from format_library.configuration import DEFAULTS
from format_library.files import file_hash, digest, write_json
from format_library.progress import WaitProgress, announce, concise, duration


def compare(config, folder, manifest, staged, attempt, support):
    """Submit original/native evidence and require a completed, matching static review."""
    settings={**DEFAULTS, **(config or {})}
    announce('Preparing original and generated sources for behavior comparison...')
    config_path=Path(settings['comparison_config_path']).resolve()
    original=[str((folder/item['path']).resolve()) for item in manifest['files']]
    jars=[str((folder/item['path']).resolve()) for item in manifest['binaries']]
    targets=[dict(original_class=name,generated_class=native) for name,native in sorted(manifest['native_classes'].items())]
    request=dict(schema_version='java-behavior-comparison-request-v1',targets=targets,
        original=dict(sources=original,dependency_sources=[],jars=jars,encoding=manifest.get('source_encoding','UTF-8'),
                      entry_methods=['format','unformat','initializeFrom','beforeFormatDo','beforeUnformatDo']),
        generated=dict(sources=[str(staged.resolve())],dependency_sources=[str(path.resolve()) for path in support],jars=[],encoding='UTF-8',
                       entry_methods=['format','unformat']))
    request_path=attempt/'comparison-request.json';write_json(request_path,request)
    try:
        roots=[Path(path) for path in original+jars]+[staged,*support]
        files={str(path.resolve()):file_hash(path) for root in roots
               for path in (sorted(root.rglob('*')) if root.is_dir() else [root]) if path.is_file()}
        input_hash=digest(dict(files=files,targets=targets,encodings=dict(original=request['original']['encoding'],generated='UTF-8'),
                               entry_methods={side:request[side]['entry_methods'] for side in ('original','generated')}))
        config_hash=file_hash(config_path)
        common_path=Path(settings['_common_config_path']) if settings.get('_common_config_path') else None
        common_hash=file_hash(common_path) if common_path else None
        environment=os.environ.copy()
        if settings.get('java_home'):
            environment['JAVA_HOME']=settings['java_home']
            environment['PATH']=str(Path(settings['java_home'])/'bin')+os.pathsep+environment.get('PATH','')
        command=[*settings['comparison_command'],'compare','--config',str(config_path),'--request',str(request_path.resolve()),
                 '--output',str((attempt/'comparison-work').resolve())]
        if common_path:
            command+=['--common-config',str(common_path)]
        progress_path=attempt/'comparison-progress.json'
        environment['JAVA_BEHAVIOR_PROGRESS_PATH']=str(progress_path.resolve())
        announce('Comparing behavior: analyzing source code before model review...')
        with WaitProgress('Behavior comparison',settings['comparison_timeout_seconds'],snapshot=progress_path):
            result=subprocess.run(command,capture_output=True,text=True,encoding='utf-8',errors='replace',
                                  timeout=settings['comparison_timeout_seconds'],env=environment)
        (attempt/'comparator.stdout.txt').write_text(result.stdout,encoding='utf-8')
        (attempt/'comparator.stderr.txt').write_text(result.stderr,encoding='utf-8')
        report=json.loads(result.stdout)
        if not isinstance(report,dict) or report.get('schema_version')!='java-behavior-comparison-v1':
            raise ValueError('Invalid comparator report schema')
        write_json(attempt/'comparison.json',report)
        decision=report.get('decision');exit_codes=dict(consistent_in_review=0,differences_found=1,inconclusive=2,error=3)
        if decision not in exit_codes or result.returncode!=exit_codes[decision]:
            raise ValueError('Comparator exit code and decision disagree')
        if decision=='error': raise ValueError('Comparator error: '+str(report.get('error','see comparison.json')))
        if report.get('files')!=files or report.get('input_hash')!=input_hash or report.get('targets')!=targets:
            raise ValueError('Comparator report does not match the original/generated evidence')
        current={str(path.resolve()):file_hash(path) for root in roots
                 for path in (sorted(root.rglob('*')) if root.is_dir() else [root]) if path.is_file()}
        if current!=files or file_hash(config_path)!=config_hash or (common_path and file_hash(common_path)!=common_hash):
            raise ValueError('Comparison inputs or comparator settings changed during review')
        if report.get('evidence_level')!='static_analysis' or not isinstance(report.get('remarks'),list):
            raise ValueError('Comparator omitted its analysis level or repair remarks')
        write_json(attempt/'comparison-feedback.json',dict(decision=decision,evidence_level='static_analysis',
            remarks=report['remarks'],findings=report.get('findings',[]),source_locations=report.get('source_locations',{})))
        if decision!='consistent_in_review' or report.get('complete') is not True:
            reason='; '.join(concise(item.get('message',''),160) for item in report['remarks'][:2] if isinstance(item,dict))
            raise ValueError('Behavior comparison '+decision+': '+reason+'; see '+str(attempt/'comparison-feedback.json'))
        announce('Behavior comparison passed within the reviewed scope.')
        return report
    except (ValueError,OSError,subprocess.SubprocessError) as error:
        write_json(attempt/'comparison-error.json',dict(status='not_accepted',message=str(error)))
        reason='Behavior comparison timed out after '+duration(error.timeout) if isinstance(error,subprocess.TimeoutExpired) else str(error)
        raise ValueError('Behavior comparison did not accept the candidate: '+reason) from error
