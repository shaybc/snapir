"""Project saved indexing and boundary reports; never parse original workspace sources."""
import json


def _saved_report(path, directory, limitations):
    """Bound memory when older reports contain very large embedded source evidence."""
    if not path.is_file():
        return None
    if path.is_symlink() or not path.resolve().is_relative_to(directory):
        limitations.append('Saved report outside the run was not read: ' + path.name)
        return None
    try:
        if path.stat().st_size > 32 * 1024 * 1024:
            limitations.append('Saved report exceeds the 32 MiB dashboard metadata limit: ' + path.name)
            return None
        with path.open(encoding='utf-8-sig') as stream:
            return json.load(stream)
    except (OSError, ValueError, RecursionError):
        limitations.append('Saved report is incomplete or unreadable: ' + path.name)
        return None


def saved_components(directory):
    """Read named saved reports for index and method-analysis drill-down, not new analysis."""
    components, limitations, files = [], [], []
    locations = [directory] + sorted(path.parent.parent for path in directory.glob('**/reports/1_intake_and_legacy_analysis'))
    seen = set()
    for root in locations:
        if root in seen:
            continue
        seen.add(root)
        index_path = root / 'reports/1_intake_and_legacy_analysis/java_source_index.json'
        index = _saved_report(index_path, directory, limitations)
        if isinstance(index, dict):
            files.append(index_path.relative_to(directory).as_posix())
            for name, sources in index.get('classes', {}).items():
                components.append(dict(name=name, kind='indexed source', status='indexed',
                    sources=sources, project=index.get('class_projects', {}).get(name),
                    evidence_file=index_path.relative_to(directory).as_posix(),
                    detail='Saved source index entry; indexing does not establish method analysis or conversion success.'))
    for path in sorted(directory.glob('**/reports/3_dependency_closure_and_component_conversion/behavior_verification_boundaries.json')):
        report = _saved_report(path, directory, limitations)
        if not isinstance(report, dict):
            continue
        files.append(path.relative_to(directory).as_posix())
        for identity, boundary in report.get('boundaries', {}).items():
            if not isinstance(boundary, dict):
                continue
            metadata = {key: value for key, value in boundary.items() if key in {
                'kind', 'implementation_class', 'analysis_status', 'issues', 'legacy_method',
                'format_lifecycles', 'analysis_tool_hash', 'analysis_classpath_hash'}}
            components.append(dict(name=boundary.get('implementation_class') or identity, identity=identity,
                kind='saved boundary analysis', status=boundary.get('analysis_status', 'not recorded'),
                evidence_file=path.relative_to(directory).as_posix(), details=metadata))
    if not components:
        limitations.append('No readable saved source index or boundary analysis metadata was found; no analysis was rerun.')
    return dict(components=components, limitations=limitations, files=files)
