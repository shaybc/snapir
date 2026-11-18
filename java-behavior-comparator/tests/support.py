"""Synthetic source inputs and a scripted model; no production API or application execution."""
import json
from pathlib import Path
from comparator.configuration import DEFAULTS


def sources(tmp_path, original=None, generated=None):
    old=tmp_path/'original';new=tmp_path/'generated';old.mkdir();new.mkdir()
    (old/'Old.java').write_text(original or 'package old; public class Old { public String format(String v){return v;} }')
    (new/'New.java').write_text(generated or 'package nativecode; public class New { public String format(String v){return v;} }')
    return dict(schema_version='java-behavior-comparison-request-v1',targets=[dict(original_class='old.Old',generated_class='nativecode.New')],
        original=dict(sources=[str(old)],encoding='UTF-8',entry_methods=['format']),
        generated=dict(sources=[str(new)],encoding='UTF-8',entry_methods=['format']))


def settings(**overrides):
    return dict(DEFAULTS,model_name='test-model',model_base_url='http://localhost/v1',**overrides)


def answer(stage, payload, difference=False):
    if stage=='boundary':
        return dict(input_mapping='Same String input.',output_mapping='Same String representation.',
            context_mapping='No context state in this fixture.',exception_mapping='Same exceptions.',uncertainties=[])
    if stage=='inventory':
        chunk=payload['evidence'][payload['primary']]
        return dict(behaviors=[dict(description='Return the input string',conditions='For each supplied String input',
            result='Return the input',exceptions='None in fixture',context_effects='No state changes',state_fields=[],
            covered_facts=[fact['id'] for fact in chunk['facts']])],ignored_facts=[],no_behavior_reason='')
    if stage=='mapping':
        candidates=[chunk['id'] for chunk in payload['generated_catalog'] if chunk['kind']=='method']
        return dict(candidates=candidates,reason='Native method implements the same contract.')
    if stage=='coverage':
        return dict(status='accounted',behaviors=[behavior['id'] for behavior in payload['original_behaviors']],
                    reason='The generated return corresponds to the original behavior.')
    if stage in {'compare','interaction','review_difference'}:
        return dict(verdict='difference' if difference else 'consistent',explanation='Different constant returned.' if difference else 'Both return the input.',
            original_outcome='Input string',generated_outcome='Different string' if difference else 'Input string',
            suggested_action='Restore the original return value.' if difference else 'No correction identified.',
            counterexample='Input abc: original abc, generated changed' if difference else '',
            original_evidence=[next(iter(payload['original_evidence']))],generated_evidence=[next(iter(payload['generated_evidence']))])
    raise AssertionError(stage)


class Model:
    def __init__(self, difference=False): self.calls=[];self.difference=difference
    def __call__(self, settings, stage, prompt, payload, timeout):
        self.calls.append(stage)
        return json.dumps(answer(stage,payload,self.difference))
