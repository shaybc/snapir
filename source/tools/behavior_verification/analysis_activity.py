"""Recognize advancing analyzer work, excluding liveness/watchdog messages."""
import re
from time import monotonic


class AnalysisActivity:
    """Keep last meaningful stage and increasing output counters, ignoring elapsed timestamps."""
    def __init__(self):
        self.last_progress = 'waiting for Java analyzer startup'
        self.last_diagnostic = self.last_progress
        self.last_activity = monotonic()
        self.seen = set()
        self.entry = None
        self.output_bytes = 0

    def observe(self, line):
        """Return true only for new work or bytes actually reported as written."""
        self.last_diagnostic = line
        match = re.match(r'^Boundary progress \+[0-9.]+s: (.*)$', line)
        if match is None: return False
        stage = match[1]
        if stage.startswith('slow operation '): return False
        output = re.match(r'XML output bytes=(\d+)', stage)
        if output:
            size = int(output[1])
            if size <= self.output_bytes: return False
            self.output_bytes = size
        else:
            prefixes = ('reading input manifest', 'scope ', 'parsing source ', 'project ', 'entry ',
                        'reachable node ', 'node complete ', 'reachability traversal complete')
            entry = re.match(r'entry (\S+) resolving ', stage)
            if entry: self.entry = entry[1]
            key = (self.entry, stage)
            if not stage.startswith(prefixes) or key in self.seen: return False
            self.seen.add(key)
        self.last_progress = line
        self.last_activity = monotonic()
        return True
