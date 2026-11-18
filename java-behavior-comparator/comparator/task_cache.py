"""Reuse exact validated AI tasks independently of scheduler/report implementation changes."""
import json
from pathlib import Path
import re
from comparator.models import digest, save, Incomplete

CONTRACT = 'java-behavior-task-v1'
# Support interrupted work from the immediately preceding implementation even without a final report.
PREVIOUS_IMPLEMENTATION = '7b99f744133bf37f468cd429acce11935e077bff844c5616e878fa2821b00d15'


class TaskCache:
    """Match model identity and exact task inputs; legacy receipts are revalidated by Tasks before migration."""
    def __init__(self, settings, work):
        self.settings, self.work = settings, Path(work)
        self.legacy = {PREVIOUS_IMPLEMENTATION, settings.get('implementation_hash', '')} - {''}
        expected = dict(provider=settings['model_provider'], name=settings['model_name'], endpoint_hash=digest(settings['model_base_url']))
        for report in sorted((self.work.parent/'runs').glob('*/report.json')):
            try:
                value = json.loads(report.read_text(encoding='utf-8'))
                identity = value.get('implementation_hash', '')
                if value.get('model') == expected and isinstance(identity,str) and re.fullmatch('[0-9a-f]{64}', identity):
                    self.legacy.add(identity)
            except (OSError, ValueError, AttributeError):
                continue

    def key(self, stage, prompt, payload, implementation=CONTRACT):
        """Retain the legacy key formula while replacing whole-code validity with a versioned task contract."""
        model_settings = {key:self.settings[key] for key in ('model_provider','model_name','model_base_url')}
        model_settings['implementation_hash'] = implementation
        return digest(dict(stage=stage,prompt=prompt,payload=payload,settings=model_settings))

    def path(self, stage, prompt, payload):
        """Return the canonical receipt path for a task's current semantic inputs."""
        return self.work/'tasks'/stage/(self.key(stage,prompt,payload)+'.json')

    def load(self, stage, prompt, payload):
        """Load an exact modern/legacy receipt; tampered response hashes fail closed."""
        current = self.path(stage,prompt,payload)
        paths = [current, *(self.work/'tasks'/stage/(self.key(stage,prompt,payload,version)+'.json') for version in sorted(self.legacy))]
        for path in paths:
            if not path.is_file():
                continue
            try:
                cached = json.loads(path.read_text(encoding='utf-8'))
                if not isinstance(cached,dict) or cached.get('response_hash') != digest(cached.get('response')):
                    raise ValueError('response hash mismatch')
                if path == current and cached.get('cache_contract') != CONTRACT:
                    raise ValueError('task contract mismatch')
            except (ValueError, OSError) as error:
                raise Incomplete('Changed task cache: '+str(path)) from error
            return cached['response'],path
        return None

    def store(self, stage, prompt, payload, response, *, migrated_from=None):
        """Persist only responses that passed the current evidence/schema validator; leave old receipts intact."""
        value = dict(response=response,response_hash=digest(response),cache_contract=CONTRACT)
        if migrated_from is not None:
            value['migrated_from'] = str(migrated_from)
        save(self.path(stage,prompt,payload),value)
