"""Translate actual mapper completions into intake counters without counting repeated heartbeats."""

import re


class IndexedMapperProgress:
    """Observe bounded mapper output; only a changed completion count advances work."""
    patterns=(
        ('Capturing mapper source revisions',r'Analysis snapshot: (\d+) files captured',False),
        ('Resolving stored Java dependencies',r'(?:Reused/resolved|Resolved) Java dependencies: (\d+) source files',False),
        ('Counting original operation consumers',r'Counted original operation consumers: (\d+) operations',False),
        ('Indexing mapper source definitions',r'Indexing source (\d+)/(\d+)',True),
        ('Mapping operation views',r'Completed operation .*?processed=(\d+)/(\d+)',True),
        ('Rendering mapper inventory',r'Inventory (\d+)/(\d+)',True),
        ('Publishing finalized mapper notes',r'Rendered indexed note (\d+)/(\d+)',True),
    )

    def __init__(self,work):
        self.work,self.phase,self.completed=work,None,0

    def __call__(self,line):
        for phase,pattern,total in self.patterns:
            match=re.search(pattern,line)
            if match is None:
                continue
            count=int(match[1])
            if self.phase!=phase:
                self.phase,self.completed=phase,0
                self.work.stage(phase,int(match[2]) if total else None)
            if count>self.completed:
                self.work.advance(count-self.completed,detail=line[-1000:])
                self.completed=count
            return
