"""Export an AI evidence report beside the run without altering migration artifacts."""
import hashlib
import json
from pathlib import Path
import re

from tools.run_diagnostics.ai_attempt_evidence import material_text
from tools.run_diagnostics.conversion_ai import format_report
from tools.run_diagnostics.request_materials import export_embedded_materials


def _write(destination, root, text):
    if destination.is_symlink() or not destination.resolve().is_relative_to(root.resolve()):
        raise ValueError('Diagnostic export must stay inside its destination')
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_bytes(text.encode('utf-8', errors='surrogatepass'))


def export_conversion_report(directory, project, report):
    """Copy only saved materials; checksum failures stay explicit and never trigger reconstruction."""
    directory, project = Path(directory).resolve(), Path(project).resolve()
    destination = project / 'work/diagnostics' / directory.name
    if destination.is_symlink() or not destination.resolve().is_relative_to(project):
        raise ValueError('Diagnostic destination must remain inside the project')
    data = report.model_dump(mode='json')
    copied = set()
    for target in data['targets']:
        target['observed_at'] = report.observed_at
        for attempt in target['attempts'] + target['budget_checks']:
            references = list(attempt.get('materials', {}).items())
            references.extend(('error', delivery['error_material']) for delivery in attempt.get('deliveries', []) if delivery.get('error_material'))
            for name, reference in references:
                try:
                    body = material_text(directory, reference)
                    if body is None:
                        raise ValueError('Material was not retained')
                    identity = hashlib.sha256(body.encode('utf-8', errors='surrogatepass')).hexdigest()
                    folder = destination / 'materials' / identity
                    path = folder / ('request.json' if name == 'request' else name + '.txt')
                    _write(path, destination, body)
                    reference['exported_file'] = path.relative_to(destination).as_posix()
                    if name == 'request' and identity not in copied:
                        payload = json.loads(body)
                        export_embedded_materials(directory, payload, folder)
                        copied.add(identity)
                except (OSError, ValueError, RecursionError, TypeError):
                    reference['export_error'] = 'Saved material is unavailable, unreadable or failed verification; no reconstruction performed.'
        label = re.sub(r'[^A-Za-z0-9._-]', '_', target['name'])[:72] or 'target'
        identity = hashlib.sha256(target['identity'].encode()).hexdigest()[:12]
        _write(destination / 'targets' / (label + '-' + identity + '.json'), destination,
               json.dumps(target, indent=2, ensure_ascii=True))
    _write(destination / 'conversion-ai-summary.json', destination, json.dumps(data, indent=2, ensure_ascii=True))
    _write(destination / 'conversion-ai-summary.txt', destination, '\n'.join(format_report(report)) + '\n')
    return ['Conversion AI report: ' + str(destination / 'conversion-ai-summary.txt'),
            'Target histories and saved request/response materials: ' + str(destination)]
