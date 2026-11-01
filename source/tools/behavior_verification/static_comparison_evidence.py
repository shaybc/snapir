"""Bind optional JVM observations to the exact current source and candidate revisions."""
import hashlib
from models.boundary_comparison_report import BoundaryComparisonReport


def comparison_cases(report, boundary, files, trusted_harness_sources=()):
    """Only the trusted harness caller supplies reports/bridges, never a generation reply."""
    if report is None:
        return []
    report = BoundaryComparisonReport.model_validate(report)
    if (report.unit_id, report.source_manifest_hash, report.configuration_hash) != (
        boundary.unit_id, boundary.source_manifest_hash, boundary.configuration_hash):
        raise ValueError('Comparison report belongs to another unit/source/configuration')
    expected = {path: hashlib.sha256(content.encode()).hexdigest() for path, content in files.items()
                if path.startswith('src/main/java/')}
    bridges = {source['path']: hashlib.sha256(source['content'].encode()).hexdigest() for source in trusted_harness_sources}
    if expected.keys() & bridges.keys():
        raise ValueError('Harness sources cannot replace candidate sources')
    actual = {}
    for key, fingerprint in report.artifact_hashes.items():
        if not key.startswith('native:compiled_text:'):
            continue
        path = key[len('native:compiled_text:'):]
        canonical = path if path.startswith('src/main/java/') else 'src/main/java/' + path
        if canonical in actual:
            raise ValueError('Duplicate comparison source identity')
        actual[canonical] = fingerprint
    if actual != {**expected, **bridges}:
        raise ValueError('Comparison report candidate sources do not match current Java files')
    return [case for case in report.cases if case['legacy']['status'] == case['native']['status'] == 'completed']
