"""Structured review-limit failures shared by task execution, scheduling and reports."""
from comparator.models import Incomplete


class LimitReached(Incomplete):
    """Identify the exact configured limit that prevented review work from proceeding."""
    def __init__(self, setting, used, limit, stage, detail=''):
        self.setting, self.used, self.limit, self.stage = setting, used, limit, stage
        self.detail = detail
        message = setting+' exhausted in '+stage+': '+str(used)+' used / '+str(limit)+' limit'
        if setting == 'request_character_limit':
            message += '; no source was truncated'
        if detail:
            message += '; '+detail
        super().__init__(message)

    def record(self):
        """Return enough data for a caller to change the correct setting or investigate failed responses."""
        return dict(setting=self.setting,used=self.used,limit=self.limit,stage=self.stage,detail=self.detail)
