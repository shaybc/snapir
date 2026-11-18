"""Bounded, resumable AI tasks with validated JSON and evidence-preserving expansion."""
import json
import time
from pathlib import Path
from comparator.models import save, Incomplete
from comparator.task_cache import TaskCache
from comparator.review_limits import LimitReached
from comparator import model_client
from comparator import progress


class Tasks:
    """Own retry limits and task receipts; malformed responses never become accepted evidence."""
    def __init__(self,settings,work,chunks,ask=None):
        self.settings=settings;self.work=work;self.chunks=chunks;self.calls=0
        self.started=time.monotonic();self.ask=ask or model_client.request
        self.cache=TaskCache(settings,work)
        self.calls_by_stage={};self.cached_receipts=set();self.migrated_receipts=set();self.limit_hits={}
        self.max_request_characters=0;self.max_attempts_used=0;self.max_evidence_used=0
        self.mapping_reuse=dict(preferred_pages=0,preferred_matches=0)

    def call(self,stage,prompt,payload,validate,allowed,*,cached_only=False):
        payload=dict(payload);extras={}
        for expansion in range(self.settings['max_evidence_rounds']):
            current={**payload,'extra_evidence':extras}
            cached=self.cache.load(stage,prompt,current)
            if cached_only and cached is None: return None
            size=len(json.dumps(current,ensure_ascii=False))+len(prompt)
            self.max_request_characters=max(self.max_request_characters,size)
            self.max_evidence_used=max(self.max_evidence_used,expansion+1)
            if size>self.settings['request_character_limit']:
                self._limit('request_character_limit',size,stage)
            path=self.cache.path(stage,prompt,current)
            if cached is not None:
                progress.update(stage,'cached',model_call=self.calls)
                value,previous_path=cached
                try:
                    self._validate(value,validate,allowed,current)
                except (ValueError,TypeError,KeyError) as error:
                    raise Incomplete('Cached response failed current evidence validation: '+str(error)) from error
                self.cached_receipts.add(str(path))
                if previous_path!=path:
                    self.cache.store(stage,prompt,current,value,migrated_from=previous_path)
                    self.migrated_receipts.add(str(path))
            else:
                error='';value=None
                for attempt in range(self.settings['max_model_attempts']):
                    remaining=self.settings['max_run_seconds']-(time.monotonic()-self.started)
                    if self.calls>=self.settings['max_model_calls']:
                        self._limit('max_model_calls',self.calls,stage)
                    if remaining<=0:
                        self._limit('max_run_seconds',round(time.monotonic()-self.started,2),stage)
                    self.calls+=1
                    self.calls_by_stage[stage]=self.calls_by_stage.get(stage,0)+1
                    self.max_attempts_used=max(self.max_attempts_used,attempt+1)
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
                        self.cache.store(stage,prompt,current,value)
                        break
                    except (ValueError,TypeError,KeyError) as problem:
                        error=str(problem)
                        save(path.with_suffix('.error.json'),dict(error=error,attempt=attempt+1))
                else: self._limit('max_model_attempts',self.settings['max_model_attempts'],stage,error)
            if value.get('need_evidence'):
                for identity in value['need_evidence']: extras[identity]=self.chunks[identity]
                continue
            return value
        self._limit('max_evidence_rounds',self.settings['max_evidence_rounds'],stage)

    def _limit(self,setting,used,stage,detail=''):
        """Retain the actual exhausted setting and counters instead of one ambiguous budget error."""
        error=LimitReached(setting,used,self.settings[setting],stage,detail)
        self.limit_hits[setting]=error.record()
        raise error

    def budget_summary(self):
        """Report measured usage and rejected work, not exhaustion inferred from equality alone."""
        used=dict(max_model_calls=self.calls,max_run_seconds=round(time.monotonic()-self.started,2),
            request_character_limit=self.max_request_characters,max_model_attempts=self.max_attempts_used,
            max_evidence_rounds=self.max_evidence_used)
        return {key:dict(limit=self.settings[key],used=value,exhausted=key in self.limit_hits)
                for key,value in used.items()}

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
