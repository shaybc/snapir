"""Fingerprint the controlled JVM and comparison implementation without recording environment values."""
import hashlib
import json
import os
import platform
import sys
from pathlib import Path
import pydantic
import pydantic_core
from runtime.java_toolchain import java_environment


def _file_digest(path):
    """Hash executable/library files without loading an entire runtime image into memory."""
    with path.open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()


def runtime_fingerprint():
    """Bind reusable observations to exact executables, JVM options, cwd and Python policy code."""
    environment=java_environment() or os.environ
    home=Path(environment['JAVA_HOME']).resolve()
    suffix='.exe' if os.name=='nt' else ''
    digest=lambda value:hashlib.sha256(value).hexdigest()
    source=Path(__file__).resolve().parents[2]
    files={}
    for folder in ('tools/behavior_verification','runtime/behavior_conversion','models'):
        for path in sorted((source/folder).rglob('*.py')):
            files[path.relative_to(source).as_posix()]=digest(path.read_bytes())
    for name in ('constants.py','runtime/java_toolchain.py'):
        path=source/name;files[name]=_file_digest(path) if path.is_file() else None
    data=dict(version='comparison-runtime-v1',system=platform.system(),machine=platform.machine(),
        system_version=platform.version(),python_version=sys.version,python_executable=str(Path(sys.executable).resolve()),
        python_binary=_file_digest(Path(sys.executable)),pydantic=pydantic.__version__,pydantic_core=pydantic_core.__version__,
        cwd=str(Path.cwd().resolve()),java_home=str(home),
        executables={name:_file_digest(home/'bin'/(name+suffix)) for name in ('java','javac')},
        libraries={name:_file_digest(home/name) for name in ('lib/modules','lib/tzdb.dat','conf/security/java.security') if (home/name).is_file()},
        release=digest((home/'release').read_bytes()),code=files,
        jvm_options={name:digest(environment.get(name,'').encode()) for name in
                     ('JAVA_TOOL_OPTIONS','JDK_JAVA_OPTIONS','_JAVA_OPTIONS','CLASSPATH','HOME','USERPROFILE','USERNAME','LANG','LC_ALL','TZ')})
    return digest(json.dumps(data,sort_keys=True).encode())
