"""Export a self-contained offline dashboard from saved diagnostic evidence."""
from collections import Counter
from datetime import datetime, timezone
import json
import hashlib
from pathlib import Path
import shutil
from urllib.parse import quote

from cli.workflow_progress_snapshot import progress_snapshot
from tools.run_diagnostics.component_evidence import saved_components
from tools.run_diagnostics.conversion_ai_export import _write
from tools.run_diagnostics.target_status import target_status, target_summary


def _file_link(path, destination):
    """Only link existing regular files contained in this diagnostic export."""
    path = destination / path
    if path.is_symlink() or not path.resolve().is_relative_to(destination) or not path.is_file():
        return None
    return quote(path.relative_to(destination).as_posix(), safe='/')


def export_html_report(directory, project, *, conversion=False, diagnostic_lines=()):
    """Write local assets and metadata; large captured bodies stay in linked files."""
    directory, project = Path(directory).resolve(), Path(project).resolve()
    destination = project / 'work/diagnostics' / directory.name
    if destination.is_symlink() or not destination.resolve().is_relative_to(project):
        raise ValueError('Diagnostic destination must remain inside the project')
    progress = progress_snapshot(directory)
    targets, limitations, analysis_failures = [], [], []
    observed_at = datetime.now(timezone.utc).isoformat()
    if conversion:
        # Consume the exporter output so every material link names the exact exported snapshot.
        summary_path = destination / 'conversion-ai-summary.json'
        if summary_path.is_symlink() or not summary_path.resolve().is_relative_to(destination):
            raise ValueError('Diagnostic summary must remain inside its destination')
        summary = json.loads(summary_path.read_text(encoding='utf-8'))
        targets, limitations = summary['targets'], summary['limitations']
        observed_at = summary['observed_at']
        analysis_failures = summary.get('analysis_failures', [])
    by_id = {target['identity']: target for target in targets}
    dependents = {}
    for target in targets:
        for prerequisite in target.get('prerequisites', []):
            dependents.setdefault(prerequisite, []).append(target['identity'])
    scanned_folders = set()
    for target in targets:
        target['status'] = target_status(target)
        target['summary'] = target_summary(target)
        target['dependents'] = dependents.get(target['identity'], [])
        target['prerequisite_statuses'] = {identity: target_status(by_id[identity]) if identity in by_id else 'not recorded'
                                           for identity in target.get('prerequisites', [])}
        for attempt in target['attempts'] + target['budget_checks']:
            for reference in attempt.get('materials', {}).values():
                if reference.get('exported_file'):
                    reference['href'] = _file_link(reference['exported_file'], destination)
            for delivery in attempt.get('deliveries', []):
                reference = delivery.get('error_material') or {}
                if reference.get('exported_file'):
                    reference['href'] = _file_link(reference['exported_file'], destination)
    evidence = saved_components(directory)
    # Earlier-stage metadata is a saved-evidence view, not a diagnosis or a new source scan.
    limitations.extend(evidence['limitations'])
    limitations.append('Saved progress and filesystem evidence are read separately; an active run can advance during export. Rerun the diagnostic to refresh.')
    files = []
    current_paths = {'conversion-ai-summary.txt', 'conversion-ai-summary.json'} if conversion else set()
    for name in evidence['files']:
        original = directory / name
        relative = 'evidence/' + hashlib.sha256(name.encode()).hexdigest()[:12] + '/' + original.name + '.txt'
        target = destination / relative
        if original.is_symlink() or not original.resolve().is_relative_to(directory):
            continue
        _write(target, destination, '')
        shutil.copyfile(original, target)
        current_paths.add(relative)
        href = _file_link(relative, destination)
        for component in evidence['components']:
            if component['evidence_file'] == name:
                component['href'] = href
    for target in targets:
        for attempt in target['attempts'] + target['budget_checks']:
            for reference in attempt.get('materials', {}).values():
                if reference.get('href'):
                    current_paths.add(reference['exported_file'])
                    folder = (destination / reference['exported_file']).parent
                    paths = [] if folder in scanned_folders else folder.rglob('*')
                    scanned_folders.add(folder)
                    for path in paths:
                        if path.is_file() and not path.is_symlink() and path.resolve().is_relative_to(destination):
                            current_paths.add(path.relative_to(destination).as_posix())
            for delivery in attempt.get('deliveries', []):
                reference = delivery.get('error_material') or {}
                if reference.get('href'):
                    current_paths.add(reference['exported_file'])
    for name in sorted(current_paths):
        href = _file_link(name, destination)
        if href:
            files.append(dict(path=name, href=href))
    data = dict(run_id=directory.name, observed_at=observed_at, progress=progress,
        conversion=conversion, targets=targets, analysis_failures=analysis_failures, counts=dict(Counter(item['status'] for item in targets)),
        saved_evidence=evidence['components'], limitations=limitations, files=files,
        folder=str(destination), folder_url=destination.as_uri() + '/', diagnostic_lines=list(diagnostic_lines))
    # Source/error text must never terminate a script element or become executable markup.
    encoded = json.dumps(data, ensure_ascii=True).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026')
    _write(destination / 'assets/report-data.js', destination, 'window.diagnosticReport = ' + encoded + ';\n')
    assets = Path(__file__).parent / 'html_assets'
    for name in ('index.html', 'dashboard.css', 'dashboard.js'):
        _write(destination / ('index.html' if name == 'index.html' else 'assets/' + name), destination,
               (assets / name).read_text(encoding='utf-8'))
    return ['HTML diagnostic dashboard: ' + str(destination / 'index.html')]
