"""Resolve only explicitly bound Eclipse containers or a configured WebSphere runtime."""

from pathlib import Path


def container_libraries(reference, variables, bindings):
    """Return proven container library paths, or None when the container remains unresolved."""
    if reference in bindings:
        return [Path(path) for path in bindings[reference]] or None
    if 'com.ibm.ws.ast.st.runtimeTarget' in reference or reference.startswith(
        'org.eclipse.jst.server.core.container/com.ibm.ws.ast.st.runtime.runtimeTarget.v85/'):
        runtime = variables.get('APP_SERVER_PATH')
        if runtime and Path(runtime).is_dir():
            try:
                libraries = sorted(Path(runtime).rglob('*.jar'))
            except OSError:
                return None
            return libraries or None
    return None
