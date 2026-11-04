"""Retain immutable analysis-tool bytes so later builds cannot invalidate receipts."""
import hashlib
import os
import tempfile
from pathlib import Path


def snapshot_tool(source,directory):
    """Pin exact bytes under their hash; reject changed sources or existing snapshots."""
    source=Path(source).resolve();raw=source.read_bytes();expected=hashlib.sha256(raw).hexdigest()
    directory=Path(directory).resolve();directory.mkdir(parents=True,exist_ok=True)
    target=directory/(expected+'.jar')
    if not target.exists():
        descriptor,name=tempfile.mkstemp(prefix='.tool-',suffix='.jar',dir=directory)
        temporary=Path(name)
        try:
            with os.fdopen(descriptor,'wb') as stream:stream.write(raw)
            try:os.link(temporary,target)
            except FileExistsError:pass
        finally:temporary.unlink(missing_ok=True)
    if hashlib.sha256(target.read_bytes()).hexdigest()!=expected:
        raise ValueError('Retained analysis tool snapshot changed')
    if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
        raise ValueError('Analysis tool changed while creating its snapshot')
    return target
