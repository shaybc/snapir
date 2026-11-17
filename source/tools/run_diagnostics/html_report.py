"""Static saved-evidence dashboard with explicitly copied, on-demand SuperScope commands."""
from datetime import datetime, UTC
from html import escape
from pathlib import Path
import sys
import sqlite3

from tools.run_diagnostics.conversion_records import load_graph, recorded_scopes

SCRIPT = '''document.querySelectorAll('[data-copy]').forEach(button => button.addEventListener('click', async () => {
const text = document.getElementById(button.dataset.copy); text.focus(); text.select();
try { if (navigator.clipboard && window.isSecureContext) await navigator.clipboard.writeText(text.value);
else if (!document.execCommand('copy')) throw new Error('manual copy');
button.textContent = 'Command copied'; } catch { button.textContent = 'Select command and press Ctrl+C'; }
}));'''


def powershell_command(directory, focus, output=None):
    """Quote every literal for PowerShell, including apostrophes and command-substitution characters."""
    quote = lambda value: "'" + str(value).replace("'", "''") + "'"
    source = Path(__file__).resolve().parents[2]
    command = '$env:PYTHONPATH = ' + quote(source) + '; & ' + quote(sys.executable) + ' -m tools.run_diagnostics.superscope_export'
    command += ' --run ' + quote(Path(directory).resolve()) + ' --focus ' + quote(focus)
    if output:
        command += ' --output ' + quote(output)
    return command


def write_dashboard(directory, output=None):
    """Read existing records for the dashboard; no diagram, graph analysis or model is generated."""
    root = Path(directory).resolve()
    target = Path(output) if output else root / 'reports/diagnostics/index.html'
    sections, counter = [], 0
    for scope in recorded_scopes(root):
        try:
            graph = load_graph(scope)
        except (OSError, ValueError, sqlite3.Error) as error:
            sections.append('<p>Saved converter records could not be read: ' + escape(str(error)) + '</p>')
            continue
        rows = []
        for identity, node in sorted(graph.nodes.items(), key=lambda item: (item[1].get('kind') != 'operation', item[1]['label'])):
            counter += 1
            command = powershell_command(scope, identity)
            signatures = []
            for entry in node.get('entry_points', []):
                signatures.append(escape(str(entry.get('direction'))) + ': ' + escape(entry.get('signature') or entry.get('expected_signature') or 'not recorded') +
                    ' — ' + escape(entry.get('declaring_class') or 'declaring class not recorded') +
                    ' (' + escape(entry.get('role', 'selected')) + ')')
            reason = node.get('reason') or '; '.join(node.get('issues', [])) or 'No blocker recorded'
            rows.append('<tr><td><strong>' + escape(node['label']) + '</strong><br>' + escape(node['kind']) +
                '</td><td>' + escape(node.get('status', 'not_recorded')) + '<br>' + escape(node.get('decision', 'not_recorded')) +
                '</td><td>' + '<br>'.join(signatures) + '</td><td>' + escape(reason) +
                '</td><td><details><summary>SuperScope diagram</summary><p>Copy and run this command locally. The dashboard does not execute it.</p>' +
                '<textarea readonly id="command-' + str(counter) + '" aria-label="SuperScope export command">' + escape(command) +
                '</textarea><button data-copy="command-' + str(counter) + '">Copy generation command</button></details></td></tr>')
        sections.append('<section><h2>' + escape(scope.name) + '</h2><p>Converter snapshot: ' + escape(graph.snapshot_id) +
            '</p><p>' + '<br>'.join(escape(issue) for issue in graph.issues) + '</p><table><thead><tr>' +
            '<th>Component / operation</th><th>Recorded state</th><th>Entry points</th><th>Blocker / issue</th><th>On demand</th>' +
            '</tr></thead><tbody>' + ''.join(rows) + '</tbody></table></section>')
    import hashlib, base64
    script_hash = base64.b64encode(hashlib.sha256(SCRIPT.encode()).digest()).decode()
    page = ('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">' +
        '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'; script-src \'sha256-' + script_hash + '\'">' +
        '<title>Conversion diagnostics</title><style>body{font:15px system-ui;margin:24px;color:#172b4d;background:#f5f7fb}section{background:white;padding:18px;margin:18px 0}' +
        'table{border-collapse:collapse;width:100%}th,td{padding:12px;text-align:left;vertical-align:top;border-bottom:1px solid #ddd}textarea{width:96%;height:110px}button,summary{cursor:pointer}td{overflow-wrap:anywhere}</style>' +
        '</head><body><h1>Saved conversion diagnostics</h1><p>Run: ' + escape(root.name) + ' · Observed ' +
        escape(datetime.now(UTC).isoformat()) + ' · Static snapshot; rerun diagnostics to refresh.</p>' +
        '<p>Facts come from converter records. A component build/test pass does not establish a matching comparison or operation acceptance.</p>' +
        ''.join(sections) + '<script>' + SCRIPT + '</script></body></html>')
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(page, encoding='utf-8')
    return target
