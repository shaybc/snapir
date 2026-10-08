"""Resolve Java classes without silently choosing conflicting source files."""

from models.java_source_index import JavaSourceIndex


class AmbiguousJavaSourceError(ValueError):
    """A class has multiple eligible source definitions."""


def resolve_indexed_source(index: JavaSourceIndex, fqcn: str, project: str | None = None) -> str | None:
    """Return a unique source, or reject ambiguous class definitions.

    Optional project ownership restricts lookup to that project and its transitive
    references. No project priority is inferred from filesystem order.
    """
    candidates = index.classes.get(fqcn, [])
    if project is not None:
        allowed = {project}
        pending = [project]
        while pending:
            for reference in index.project_references.get(pending.pop(), []):
                if reference not in allowed:
                    allowed.add(reference)
                    pending.append(reference)
        candidates = [path for path in candidates if index.class_projects[path] in allowed]
    if len(candidates) > 1:
        raise AmbiguousJavaSourceError(f"Ambiguous Java source for {fqcn}: {', '.join(candidates)}")
    return candidates[0] if candidates else None
