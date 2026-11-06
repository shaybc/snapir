"""Adapt the historical Python API to the shared Java source-reference resolution policy."""

_UNRESOLVED_OWNER = object()


def resolve_reference(reference, document, source_index, source_path, *, owner_project=_UNRESOLVED_OWNER):
    """Resolve a reference using bounded document batches and captured project visibility.

    A discovery index is an immutable analysis snapshot; rebuild it after source or
    visibility changes. The indexed map path consumes persisted edges directly.
    """
    from tools.java_analysis_tools.source_dependencies.resolution_process import resolve_reference_batch
    return resolve_reference_batch(reference,document,source_index,source_path,
        None if owner_project is _UNRESOLVED_OWNER else owner_project,owner_project is not _UNRESOLVED_OWNER)
