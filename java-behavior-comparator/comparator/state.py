"""Bounded, resumable AI tasks with validated JSON and evidence-preserving expansion."""
import json
import time
from pathlib import Path
from comparator.models import digest, save, Incomplete
from comparator import model_client
from comparator import progress


class Tasks:
    """Own retry limits and task receipts; malformed responses never become accepted evidence."""
    def __init__(self,settings,work,chunks,ask=None):
        self.settings=settings;self.work=work;self.chunks=chunks;self.calls=0
        self.started=time.monotonic();self.ask=ask or model_client.request

    def call(self,stage,prompt,payload,validate,allowed):
        payload=dict(payload);extras={}
        for expansion in range(self.settings['max_evidence_rounds']):
            current={**payload,'extra_evidence':extras}
            if len(json.dumps(current,ensure_ascii=False))+len(prompt)>self.settings['request_character_limit']:
                raise Incomplete(stage+': complete evidence exceeds the request budget; no source was truncated')
            model_settings={key:self.settings[key] for key in ('model_provider','model_name','model_base_url','implementation_hash')}
            key=digest(dict(stage=stage,prompt=prompt,payload=current,settings=model_settings))
            path=self.work/'tasks'/stage/(key+'.json')
            if path.is_file():
                progress.update(stage,'cached',model_call=self.calls)
                cached=json.loads(path.read_text(encoding='utf-8'))
                if cached.get('response_hash')!=digest(cached.get('response')): raise Incomplete('Changed task cache: '+str(path))
                value=cached['response']
                self._validate(value,validate,allowed,current)
            else:
                error='';value=None
                for attempt in range(self.settings['max_model_attempts']):
                    remaining=self.settings['max_run_seconds']-(time.monotonic()-self.started)
                    if self.calls>=self.settings['max_model_calls'] or remaining<=0:
                        raise Incomplete('Comparison task/run budget exhausted')
                    self.calls+=1
                    sent={**current,'format_feedback':error}
                    save(path.with_suffix('.request.json'),dict(stage=stage,prompt=prompt,payload=sent))
                    try:
                        progress.update(stage,'waiting',model_call=self.calls,
                                        timeout=min(remaining,self.settings['model_timeout_seconds']))
                        text=self.ask(self.settings,stage,prompt,sent,min(remaining,self.settings['model_timeout_seconds']))
                        progress.update(stage,'received',model_call=self.calls)
                        path.parent.mkdir(parents=True,exist_ok=True)
                        path.with_suffix('.response.txt').write_text(text,encoding='utf-8')
                        value=json.loads(text);self._validate(value,validate,allowed,current)
                        save(path,dict(response=value,response_hash=digest(value)))
                        break
                    except (ValueError,TypeError,KeyError) as problem:
                        error=str(problem)
                        save(path.with_suffix('.error.json'),dict(error=error,attempt=attempt+1))
                else: raise Incomplete(stage+': '+error)
            if value.get('need_evidence'):
                for identity in value['need_evidence']: extras[identity]=self.chunks[identity]
                continue
            return value
        raise Incomplete(stage+': evidence expansion limit reached')

    @staticmethod
    def _validate(value,validate,allowed,payload):
        if not isinstance(value,dict): raise ValueError('Return a JSON object')
        need=value.get('need_evidence',[])
        if not isinstance(need,list) or any(identity not in allowed for identity in need):
            raise ValueError('Requested evidence must use supplied indexed identifiers')
        if not need:
            supplied=set()
            for key in ('evidence','original_evidence','generated_evidence','extra_evidence'):
                if isinstance(payload.get(key),dict): supplied.update(payload[key])
            for key in ('original_evidence','generated_evidence'):
                if isinstance(value.get(key),list) and any(identity not in supplied for identity in value[key]):
                    raise ValueError('Citations require actual supplied source, not unread catalog identifiers')
            validate(value)
