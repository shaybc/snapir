"""Build reproducible JARs from an explicitly owned set of compiled entries."""
import io
from pathlib import Path
from zipfile import ZipFile, ZipInfo, ZIP_DEFLATED
import re


def compiled_jar(directory, names):
    """Keep entry ordering and ZIP timestamps stable so exact deleted binaries can be restored."""
    from tools.shared_artifact_store.manifests import contained_path
    stream = io.BytesIO()
    with ZipFile(stream, 'w', ZIP_DEFLATED) as archive:
        for name in sorted(names):
            info = ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            archive.writestr(info, contained_path(directory, name).read_bytes(), compress_type=ZIP_DEFLATED)
    return stream.getvalue()


def owned_class_entries(directory, files):
    """Include nested, anonymous and package-private types declared in owned Java sources."""
    from runtime.java_public_type import _code
    result = set()
    for file in files:
        if not file.path.startswith('src/main/java/') or not file.path.endswith('.java'):
            continue
        relative = Path(file.path.removeprefix('src/main/java/'))
        code = _code(file.content)
        names = set()
        for match in re.finditer(r'\b(?:class|interface|enum|record)\s+([A-Za-z_$][\w$]*)', code):
            prefix = code[:match.start()]
            if prefix.count('{') == prefix.count('}'):
                names.add(match.group(1))
        names.add(relative.stem)
        for path in (Path(directory) / relative.parent).glob('*.class'):
            if any(path.stem == name or path.stem.startswith(name + '$') for name in names):
                result.add(path.relative_to(directory).as_posix())
    return sorted(result)
