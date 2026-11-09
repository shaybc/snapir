"""Expand Eclipse declarations in place, preserving project export boundaries."""
from pathlib import Path
from models.project_classpath import ProjectClasspathEntry


def declaration(view, kind, path, reference, exported, position, *, child=0, known=True):
    """Record a resolved declaration without inventing provider ordering."""
    view.declared.append(ProjectClasspathEntry(kind=kind, path=str(path), reference=reference,
        exported=exported, order_known=known, rank=[position, child if known else 0],
        chain=[view.directory + '/.classpath:' + str(position), reference]))


def expand_projects(index, additional=()):
    """A direct dependency exposes its sources and only its exported dependencies."""
    def expand(name, inherited=False, stack=(), prefix=(), chain=()):
        if name in stack:
            return []
        if name not in index.project_classpaths:
            message = 'Ordered classpath metadata is missing for referenced project: ' + name
            if message not in index.issues:
                index.issues.append(message)
            return []
        result = []
        for entry in index.project_classpaths[name].declared:
            if inherited and entry.kind not in {'source', 'output'} and not entry.exported:
                continue
            rank = [*prefix, *entry.rank]
            provenance = [*chain, *entry.chain]
            if entry.kind == 'project':
                children = expand(entry.path, True, (*stack, name), rank, provenance)
                if not entry.order_known:
                    children = [child.model_copy(update={'rank': rank, 'order_known': False}) for child in children]
                result.extend(children)
            else:
                result.append(entry.model_copy(update={'rank': rank, 'chain': provenance}))
        return result
    for name, view in index.project_classpaths.items():
        expanded = expand(name)
        for position, path in enumerate(additional):
            expanded.append(ProjectClasspathEntry(kind='library', path=str(Path(path).resolve()),
                reference='classpath_jars', rank=[max((entry.rank[0] for entry in view.declared), default=-1) + 1, position], chain=['classpath_jars']))
        seen, view.entries = set(), []
        for entry in expanded:
            key = (entry.kind, entry.path)
            if key not in seen:
                seen.add(key)
                view.entries.append(entry)
