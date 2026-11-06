"""Excel Generator: export Composer Mapper Markdown to an operation planning workbook.

Requires Python 3.10+ and openpyxl: python -m pip install openpyxl
Usage: python "Excel Generator.py" "path/to/mapper-output"
       python "Excel Generator.py" --vault "path/to/mapper-output" --output report.xlsx --include-relationships

This portable snapshot preserves Snapir's operation discovery and wave calculation.
Copy this file alone; no Snapir installation or Node.js runtime is required.
Supports legacy vaults and scoped channel/operation vaults with simplified resource paths.
Pass the vault root, not its channels or operations folder. Scoped vaults must include
vault-manifest.json and all listed Markdown notes; original Composer sources are not needed.
Large manifests are read incrementally with timestamped progress and a final elapsed time.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import math
import sys


def write_workbook(graph, waves, output, relationships=False):
    """Write the existing migration report views as a filterable Excel workbook."""
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.table import Table, TableStyleInfo
    from openpyxl.utils import get_column_letter

    workbook = Workbook()
    workbook.remove(workbook.active)

    def sheet(name, title, context, headers, rows, widths, table_name):
        item = workbook.create_sheet(name)
        item.sheet_view.showGridLines = False
        item.cell(2, 1, title)
        item.cell(3, 1, context)
        for column, value in enumerate(headers, 1):
            item.cell(5, column, value)
        for row_number, values in enumerate(rows, 6):
            for column, value in enumerate(values, 1):
                cell = item.cell(row_number, column, value)
                if isinstance(value, str):
                    cell.data_type = 's'
        end = max(6, 5 + len(rows))
        for row in item.iter_rows(min_row=1, max_row=end, max_col=len(headers)):
            for cell in row:
                cell.font = Font(name='Arial', size=11, color='243247')
                cell.alignment = Alignment(vertical='center', wrap_text=True)
        item['A2'].font = Font(name='Arial', size=16, bold=True, color='243247')
        item['A3'].font = Font(name='Arial', size=10, italic=True, color='58677B')
        item['A3'].alignment = Alignment(wrap_text=False)
        for cell in item[5]:
            cell.fill = PatternFill('solid', fgColor='234568')
            cell.font = Font(name='Arial', size=11, bold=True, color='FFFFFF')
            cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
        item.row_dimensions[5].height = 32
        for column, width in enumerate(widths, 1):
            item.column_dimensions[get_column_letter(column)].width = width
        for row_number, values in enumerate(rows, 6):
            lines = max(sum(max(1, math.ceil(len(line) / max(1, widths[i] - 2)))
                            for line in str(value or '').split('\n'))
                        for i, value in enumerate(values))
            item.row_dimensions[row_number].height = min(409, max(18, lines * 15))
        table = Table(displayName=table_name, ref=f'A5:{get_column_letter(len(headers))}{end}')
        table.tableStyleInfo = TableStyleInfo(name='TableStyleMedium2', showRowStripes=True)
        item.add_table(table)
        item.freeze_panes = 'A6'
        return item

    ordered = sorted(graph['operations'], key=lambda key: (waves[key]['wave'] if waves[key]['wave'] is not None else math.inf, key))
    plan = sheet('Migration Plan', 'Operation implementation order',
        'Dependencies first. Cycles require coordinated implementation; blank waves have unresolved dependencies.',
        ['Build wave', 'Channel', 'Operation', 'Implement after (direct)', 'Cycle group', 'Issue'],
        [[waves[key]['wave'], graph['operations'][key]['channel'], graph['operations'][key]['operation_id'],
          '\n'.join(waves[key]['prerequisites']) or 'None', waves[key]['cycle_group'] or 'None', waves[key]['issue']] for key in ordered],
        [15, 18, 32, 62, 45, 45], 'MigrationPlanTable')
    for row in plan.iter_rows(min_row=6, max_row=max(6, len(ordered) + 5), max_col=1):
        row[0].number_format = '0'
    operations = sheet('Operations', 'Operation inventory',
        'Counts are unique direct operation connections, not step counts or implementation effort.',
        ['Channel', 'Operation', 'Calls count', 'Callers count', 'Build wave', 'Cycle group'],
        [[graph['operations'][key]['channel'], graph['operations'][key]['operation_id'], waves[key]['calls_count'],
          waves[key]['callers_count'], waves[key]['wave'], waves[key]['cycle_group'] or 'None'] for key in sorted(graph['operations'])],
        [18, 32, 17, 17, 16, 45], 'OperationsTable')
    for row in operations.iter_rows(min_row=6, max_row=max(6, len(ordered) + 5), min_col=3, max_col=5):
        for cell in row:
            cell.number_format = '#,##0'
    if relationships:
        sheet('Relationships', 'Operation call evidence',
            'Filter Caller or Called operation. Multiple call sites are retained as evidence.',
            ['Caller', 'Called operation', 'Invoking step', 'Mapper note'],
            [[call['caller'], call['callee'], call['step'], call['note']] for call in graph['calls']],
            [42, 42, 32, 62], 'RelationshipsTable')
    if graph['issues']:
        sheet('Issues', 'Unresolved operation relationships',
            'Affected operations and their callers have no assigned build wave.',
            ['Operation', 'Step', 'Issue'],
            [[issue['operation'], issue['step'], issue['detail']] for issue in graph['issues']],
            [42, 45, 90], 'IssuesTable')
    workbook.save(output)


def main(argv=None):
    """Export a Mapper output directory without importing any Snapir modules."""
    parser = argparse.ArgumentParser(prog='Excel Generator', description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('mapper_output', nargs='?', type=Path, help='Mapper vault root; scoped vaults must include vault-manifest.json')
    parser.add_argument('--vault', type=Path, help='Alias for the Mapper output directory')
    parser.add_argument('--output', type=Path, help='Destination .xlsx; defaults beside the Mapper output folder')
    parser.add_argument('--include-relationships', action='store_true')
    args = parser.parse_args(argv)
    if (args.mapper_output is None) == (args.vault is None):
        parser.error('provide one Mapper output path, either positionally or with --vault')
    vault = (args.mapper_output or args.vault).resolve()
    output = args.output or vault.parent / 'operation-migration.xlsx'
    if output.suffix.lower() != '.xlsx':
        parser.error('--output must end in .xlsx')
    try:
        progress = ExportProgress()
        progress.phase('Validating Mapper vault and discovering operation calls')
        if is_indexed_map(vault):
            counts=export_indexed_workbook(vault,output,args.include_relationships,progress.update)
            print(f"Created {output.resolve()}: {counts['operations']} operations, {counts['calls']} call sites, {counts['issues']} issues. Elapsed={progress.elapsed()}",flush=True)
            return 0
        graph = discover_operation_calls(vault, progress=progress.update)
        progress.phase('Calculating dependency waves')
        waves = operation_waves(graph)
        output.parent.mkdir(parents=True, exist_ok=True)
        progress.phase('Writing Excel workbook')
        write_workbook(graph, waves, output, args.include_relationships)
    except ModuleNotFoundError as exc:
        if exc.name != 'openpyxl':
            raise
        parser.exit(1, 'Excel Generator requires openpyxl. Install it with: python -m pip install openpyxl\n')
    except (OSError, ValueError) as exc:
        parser.exit(1, f'Excel Generator: {exc}\n')
    print(f"Created {output.resolve()}: {len(graph['operations'])} operations, {len(graph['calls'])} call sites, {len(graph['issues'])} issues. Elapsed={progress.elapsed()}", flush=True)
    return 0

@dataclass(kw_only=True)
class ComposerOperation:
    id: str
    channel: str
    source_file: str
    source_hash: str
    operation_context: str | None = None
    host_key: str | None = None
    operation_fields: str | None = None
    write_to_log: str | None = None
    write_to_ofec_stat: str | None = None
    is_selective_journalising: str | None = None
    ini_values: list[str] = field(default_factory=list)
    steps: list[str] = field(default_factory=list)
    ref_formats: dict[str, str] = field(default_factory=dict)
    inline_format_ids: list[str] = field(default_factory=list)
    conversion_status: str

@dataclass(kw_only=True)
class ComposerOpStep:
    id: str
    parent_operation_id: str
    impl_class: str | None = None
    source_file: str
    source_hash: str
    only_for: str | None = None
    transitions: dict[str, str] = field(default_factory=dict)
    return_body_switches: dict[str, str] = field(default_factory=dict)
    parameters: dict[str, str] = field(default_factory=dict)
    conversion_status: str

# Bundled from source/tools/composer_mapper_tools/frontmatter_parser.py
import re
from typing import Any

def parse_frontmatter(md_text: str) -> dict[str, Any]:
    match = re.search('(?s)(?:^|\\n)---\\n(.*?)\\n---(?:\\n|$)', md_text)
    if match is None:
        return {}
    return _parse_yaml_subset(match.group(1))

def parse_section(md_text: str, section_heading: str) -> str:
    pattern = re.compile(f'(?ms)^##\\s+{re.escape(section_heading)}\\s*\\n(.*?)(?=^##\\s+|\\Z)')
    match = pattern.search(md_text)
    if match is None:
        return ''
    return match.group(1).strip()

def _parse_yaml_subset(text: str) -> dict[str, Any]:
    result: dict[str, Any] = {}
    current_key: str | None = None
    for raw_line in text.splitlines():
        line = raw_line.rstrip()
        if not line.strip():
            continue
        if current_key and line.startswith('  - '):
            result[current_key].append(_coerce_scalar(line[4:].strip()))
            continue
        current_key = None
        if ':' not in line:
            continue
        key, value = line.split(':', 1)
        key = key.strip()
        value = value.strip()
        if value == '[]':
            result[key] = []
        elif value == '':
            result[key] = []
            current_key = key
        else:
            result[key] = _coerce_scalar(value)
    return result

def _coerce_scalar(value: str) -> Any:
    value = value.strip().strip('"').strip("'")
    if value.lower() == 'true':
        return True
    if value.lower() == 'false':
        return False
    return value

def clean_markdown_value(value: str) -> str:
    value = value.strip()
    value = re.sub('\\[([^\\]]+)\\]\\([^)]+\\)', '\\1', value)
    value = value.replace('`', '')
    return value.strip()

def parse_bullet_values(section_text: str) -> list[str]:
    values = []
    for line in section_text.splitlines():
        stripped = line.strip()
        if stripped.startswith('- '):
            value = clean_markdown_value(stripped[2:])
            if value and value.lower() != 'none':
                values.append(value)
    return values

def parse_key_value_bullets(section_text: str) -> dict[str, str]:
    values: dict[str, str] = {}
    for item in parse_bullet_values(section_text):
        if ':' in item:
            key, value = item.split(':', 1)
            values[key.strip()] = value.strip()
        elif '->' in item:
            key, value = item.split('->', 1)
            values[key.strip()] = value.strip()
    return values

# Bundled from source/tools/composer_mapper_tools/operation_parser.py
def parse_operation_note(md_text: str, source_path: str) -> ComposerOperation:
    frontmatter = parse_frontmatter(md_text)
    ref_formats = {}
    request = _first_bullet(parse_section(md_text, 'Request Format'))
    reply = _first_bullet(parse_section(md_text, 'Reply Format'))
    if request:
        ref_formats['csRequestFormat'] = request
    if reply:
        ref_formats['csReplyFormat'] = reply
    ref_formats.update(parse_key_value_bullets(parse_section(md_text, 'Other Formats')))
    operation_attrs = parse_key_value_bullets(parse_section(md_text, 'Operation Attributes'))
    context = _first_bullet(parse_section(md_text, 'Context'))
    if context and context.lower().startswith('unresolved:'):
        context = context.split(':', 1)[1].strip()
    return ComposerOperation(id=str(frontmatter.get('entity_id', '')), channel=str(frontmatter.get('channel', '')), source_file=str(frontmatter.get('source_file', '')), source_hash=str(frontmatter.get('source_hash', '')), operation_context=context, host_key=frontmatter.get('host_key'), operation_fields=operation_attrs.get('operationFields'), write_to_log=operation_attrs.get('writeToLog'), write_to_ofec_stat=operation_attrs.get('writeToOfecStat'), is_selective_journalising=operation_attrs.get('isSelectiveJournalising'), ini_values=parse_bullet_values(parse_section(md_text, 'Initial Values (iniValue)')), steps=[_strip_step_suffix(step) for step in parse_bullet_values(parse_section(md_text, 'Steps'))], ref_formats=ref_formats, inline_format_ids=[value.removeprefix('inline:').strip() for value in parse_bullet_values(parse_section(md_text, 'Other Formats')) if value.startswith('inline:')], conversion_status=str(frontmatter.get('conversion_status', 'not_started')))

def _first_bullet(section_text: str) -> str | None:
    values = parse_bullet_values(section_text)
    return values[0] if values else None

def _strip_step_suffix(value: str) -> str:
    return clean_markdown_value(value.split(' *(', 1)[0])

# Bundled from source/tools/composer_mapper_tools/opstep_parser.py
import re

def parse_opstep_note(md_text: str, source_path: str) -> ComposerOpStep:
    frontmatter = parse_frontmatter(md_text)
    implementation = _parse_impl_class(parse_section(md_text, 'Implementation'))
    return ComposerOpStep(id=str(frontmatter.get('entity_id', '')), parent_operation_id=_first(frontmatter.get('used_by_operations', [])) or '', impl_class=implementation, source_file=str(frontmatter.get('source_file', '')), source_hash=str(frontmatter.get('source_hash', '')), only_for=frontmatter.get('onlyFor'), transitions=_parse_transitions(parse_section(md_text, 'Transitions')), return_body_switches=_parse_return_body_switches(parse_section(md_text, 'Return Body Switches')), parameters=parse_key_value_bullets(parse_section(md_text, 'Parameters')), conversion_status=str(frontmatter.get('conversion_status', 'not_started')))

def _parse_impl_class(section: str) -> str | None:
    for line in section.splitlines():
        if line.strip().startswith('- '):
            value = clean_markdown_value(line.strip()[2:])
            if value.lower() == 'unresolved':
                return None
            if value.lower().startswith('unresolved:'):
                return value.split(':', 1)[1].strip()
            return value
    return None

def _parse_transitions(section: str) -> dict[str, str]:
    transitions: dict[str, str] = {}
    for line in section.splitlines():
        value = clean_markdown_value(line.strip().removeprefix('- '))
        if ' -> ' in value:
            key, target = value.split(' -> ', 1)
            transitions[key.strip()] = target.removeprefix('unresolved ').strip()
    return transitions

def _parse_return_body_switches(section: str) -> dict[str, str]:
    switches: dict[str, str] = {}
    for line in section.splitlines():
        if not line.strip().startswith('- '):
            continue
        value = clean_markdown_value(line.strip()[2:])
        match = re.search('RC\\s+(\\S+)\\s+->\\s+switch reply body to\\s+(.+)', value)
        if match:
            switches[match.group(1)] = match.group(2).strip()
    return switches

def _first(value: object) -> str | None:
    if isinstance(value, list) and value:
        return str(value[0])
    return None

# Bundled from source/tools/composer_mapper_tools/channel_registry_parser.py
from pathlib import Path

def parse_channel_operation_registry(registry_md_path: str) -> list[tuple[str, str, str]]:
    path = Path(registry_md_path)
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        stripped = line.strip()
        if not stripped.startswith('|') or '---' in stripped or 'Operation' in stripped:
            continue
        cells = [clean_markdown_value(cell.strip()) for cell in stripped.strip('|').split('|')]
        if len(cells) >= 3:
            rows.append((cells[0], cells[1], cells[2]))
    return rows

# Bundled from source/tools/composer_mapper_tools/manifest_json_stream.py
"""Read manifest arrays incrementally using only Python's standard library."""
import json

class _ManifestJsonReader:
    """Buffer at most one JSON value plus an input chunk, rather than the whole manifest."""

    def __init__(self, stream):
        self.stream = stream
        self.buffer = ''
        self.position = 0
        self.eof = False
        self.decoder = json.JSONDecoder()

    def _fill(self):
        chunk = self.stream.read(65536)
        self.buffer = self.buffer[self.position:] + chunk
        self.position = 0
        self.eof = not chunk

    def peek(self):
        """Return the next non-whitespace character, or an empty string at EOF."""
        while True:
            while self.position < len(self.buffer) and self.buffer[self.position] in ' \t\r\n':
                self.position += 1
            if self.position < len(self.buffer):
                return self.buffer[self.position]
            if self.eof:
                return ''
            self._fill()

    def take(self, expected):
        """Consume required JSON punctuation or reject malformed input."""
        if self.peek() != expected:
            raise ValueError('Invalid scoped manifest JSON: expected ' + expected)
        self.position += 1

    def value(self):
        """Decode one value, extending the buffer only when that value spans chunks."""
        self.peek()
        while True:
            try:
                value, end = self.decoder.raw_decode(self.buffer, self.position)
            except json.JSONDecodeError:
                if self.eof:
                    raise
                self._fill()
                continue
            if end == len(self.buffer) and (not self.eof):
                self._fill()
                continue
            if end < len(self.buffer) and self.buffer[end] not in ',]}: \t\r\n':
                if self.eof:
                    raise ValueError('Invalid scoped manifest JSON value')
                self._fill()
                continue
            self.position = end
            return value

def iter_manifest_fields(path):
    """Yield field, event and value; entities/diagnostics arrays yield one item at a time.

    The stream is closed on completion or failure. Invalid/truncated JSON raises ValueError.
    Other fields and individual array items retain their ordinary JSON representation.
    """
    with path.open('r', encoding='utf-8-sig') as stream:
        reader = _ManifestJsonReader(stream)
        reader.take('{')
        if reader.peek() != '}':
            while True:
                name = reader.value()
                if not isinstance(name, str):
                    raise ValueError('Invalid scoped manifest JSON field')
                reader.take(':')
                if name in ('entities', 'diagnostics') and reader.peek() == '[':
                    reader.take('[')
                    yield (name, 'array', None)
                    if reader.peek() != ']':
                        while True:
                            yield (name, 'item', reader.value())
                            if reader.peek() != ',':
                                break
                            reader.take(',')
                    reader.take(']')
                else:
                    yield (name, 'value', reader.value())
                if reader.peek() != ',':
                    break
                reader.take(',')
        reader.take('}')
        if reader.peek():
            raise ValueError('Invalid scoped manifest JSON: trailing content')

# Bundled from source/tools/operation_call_tools/export_progress.py
"""Report Excel export phases and throttle note/operation progress messages."""
from datetime import datetime
from time import monotonic

class ExportProgress:
    """Print timestamped progress and elapsed time without changing export results."""

    def __init__(self):
        self.started = monotonic()
        self.last_update = self.started

    def elapsed(self):
        """Return total runtime in hours, minutes and seconds."""
        seconds = int(monotonic() - self.started)
        return f'{seconds // 3600:02d}:{seconds // 60 % 60:02d}:{seconds % 60:02d}'

    def phase(self, message):
        """Print a phase immediately and flush redirected or interactive console output."""
        self.last_update = monotonic()
        print(f"[{datetime.now().astimezone().strftime('%Y-%m-%d %H:%M:%S%z')}] {message} | elapsed={self.elapsed()}", flush=True)

    def update(self, message):
        """Print ongoing work at most once every five seconds."""
        if monotonic() - self.last_update >= 5:
            self.phase(message)

# Bundled from source/tools/composer_mapper_tools/indexed_analysis.py
"""Read immutable schema-four map facts without loading a workspace manifest or graph."""
from collections.abc import Sequence
import hashlib
import json
from pathlib import Path
import sqlite3
import tempfile
MAX_RECORD_BYTES = 4 * 1024 * 1024
_validated = set()

def bounded_json(value):
    """Decode one bounded record, never an array containing a complete project."""
    if len(value.encode('utf-8')) > MAX_RECORD_BYTES:
        raise ValueError('Indexed analysis record exceeds 4 MiB')
    return json.loads(value)

class SqlSequence(Sequence):
    """Hydrate one indexed row at a time, including when callers request iteration."""

    def __init__(self, conn, query, decode, parameters=()):
        self.conn, self.query, self.decode, self.parameters = (conn, query, decode, parameters)

    def __iter__(self):
        for row in self.conn.execute(self.query, self.parameters):
            yield self.decode(row)

    def __len__(self):
        return self.conn.execute('SELECT count(*) FROM (' + self.query + ')', self.parameters).fetchone()[0]

    def __getitem__(self, index):
        if isinstance(index, slice):
            raise TypeError('Iterate indexed inventory instead of slicing it into a list')
        if index < 0:
            index += len(self)
        row = self.conn.execute(self.query + ' LIMIT 1 OFFSET ?', (*self.parameters, index)).fetchone()
        if row is None:
            raise IndexError(index)
        return self.decode(row)

def digest(path):
    """Hash with bounded buffering."""
    with Path(path).open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()

class IndexedAnalysis(dict):
    """Expose compatible manifest fields as readonly SQL sequences, with an explicit lifetime."""

    def __init__(self, root, *, progress=None, validate_notes=True, receipt=None, trusted_publication=False):
        self.root = Path(root).resolve()
        descriptor = self.root / 'vault-manifest.json'
        if descriptor.stat().st_size > 65536:
            raise ValueError('Indexed map descriptor exceeds 64 KiB')
        metadata = bounded_json(descriptor.read_text(encoding='utf-8-sig'))
        self.manifest_hash = digest(descriptor)
        if metadata.get('vault_schema_version') != 4 or metadata.get('identity_version') != 1 or metadata.get('complete') is not True:
            raise ValueError('Incomplete or unsupported indexed analysis')
        if (self.root / 'vault-generation.json').exists():
            raise ValueError('Indexed map generation is incomplete')
        required = {'java-edges-v1', 'original-consumers-v1', 'context-java-roots-v1', 'indexed-xml'}
        if not required <= set(metadata.get('capabilities', [])):
            raise ValueError('Indexed map lacks required analysis capabilities; regenerate it')
        self.database = self.safe_path(metadata['analysis_store'])
        if digest(self.database) != metadata.get('analysis_hash'):
            raise ValueError('Indexed analysis database changed or is truncated')
        self.conn = sqlite3.connect(self.database.as_uri() + '?mode=ro&immutable=1', uri=True)
        self.conn.execute('PRAGMA cache_size=-8192')
        self.conn.execute('PRAGMA temp_store=FILE')
        self.source_root = Path(self.conn.execute("SELECT value FROM revision WHERE key='source_root'").fetchone()[0])
        if self.conn.execute("SELECT value FROM revision WHERE key='complete'").fetchone() != ('true',):
            raise ValueError('Indexed analysis revision is incomplete')
        if self.conn.execute('PRAGMA quick_check').fetchone() != ('ok',):
            raise ValueError('Indexed analysis database failed integrity checks')
        super().__init__(metadata)
        self['channels'] = [row[0] for row in self.conn.execute("SELECT key FROM sets WHERE collection='channels' ORDER BY key")]
        self['entities'] = SqlSequence(self.conn, 'SELECT data,note_hash FROM notes WHERE definition IS NOT NULL ORDER BY path', self._entry)
        self['operation_contexts'] = SqlSequence(self.conn, 'SELECT identity,data FROM operation_context_index ORDER BY ordinal', self._context)
        self['diagnostics'] = SqlSequence(self.conn, "SELECT data FROM records WHERE collection='diagnostics' ORDER BY ordinal", lambda row: bounded_json(row[0]))
        receipt_key = receipt
        receipt = (str(self.root), metadata['analysis_hash'], descriptor.stat().st_mtime_ns)
        proof = dict(map_root=str(self.root), manifest_hash=self.manifest_hash, analysis_hash=metadata['analysis_hash'])
        prior = None
        if receipt_key is not None:
            path = Path(receipt_key)
            if path.is_file() and path.stat().st_size <= 65536:
                try:
                    prior = bounded_json(path.read_text(encoding='utf-8'))
                except (ValueError, OSError):
                    prior = None
        if validate_notes and (not trusted_publication) and (receipt not in _validated) and (prior != proof):
            for number, (path, expected) in enumerate(self.conn.execute('SELECT path,note_hash FROM notes ORDER BY path'), 1):
                if digest(self.safe_path(path)) != expected:
                    raise ValueError('Indexed note hash mismatch: ' + path)
                if progress and (number == 1 or number % 250 == 0):
                    progress(f'Validated {number} indexed notes: {path}')
            self._validate_links()
            if len(_validated) >= 128:
                _validated.clear()
            _validated.add(receipt)
        else:
            self._validate_links()
        if validate_notes and receipt_key is not None and (prior != proof):
            path = Path(receipt_key)
            path.parent.mkdir(parents=True, exist_ok=True)
            temporary = None
            try:
                with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8', dir=path.parent, delete=False) as output:
                    output.write(json.dumps(proof))
                    temporary = Path(output.name)
                temporary.replace(path)
            finally:
                if temporary is not None:
                    temporary.unlink(missing_ok=True)

    def safe_path(self, relative):
        path = self.root / relative
        if Path(relative).is_absolute() or '..' in Path(relative).parts or (not path.resolve().is_relative_to(self.root)):
            raise ValueError('Unsafe indexed map path: ' + relative)
        return path

    @staticmethod
    def _entry(row):
        return dict(bounded_json(row[0]), note_hash=row[1])

    def entry(self, note):
        row = self.conn.execute('SELECT data,note_hash FROM notes WHERE path=? AND definition IS NOT NULL', (note,)).fetchone()
        if row is None:
            raise ValueError('Missing indexed note: ' + note)
        return self._entry(row)

    def consumers(self, definition):
        """Page qualified consumer identities without embedding a global array in each note."""
        return SqlSequence(self.conn, 'SELECT context FROM note_consumers WHERE definition=? ORDER BY context', lambda row: row[0], (definition,))

    def _context(self, row):
        identity, data = row
        size = self.conn.execute('SELECT COALESCE(sum(length(CAST(data AS BLOB))+length(key)+128),0) FROM context_parts WHERE context=?', (identity,)).fetchone()[0]
        if size + len(data.encode('utf-8')) > MAX_RECORD_BYTES:
            raise ValueError('Selected operation context exceeds the 4 MiB materialization budget: ' + identity)
        context = bounded_json(data)
        for kind in ('references', 'transition_targets'):
            context[kind] = {key: bounded_json(value)['value'] for key, value in self.conn.execute('SELECT key,data FROM context_parts WHERE context=? AND kind=? ORDER BY key', (identity, kind))}
        for kind in ('step_notes', 'calls', 'java_resolution'):
            context[kind] = [bounded_json(value)['value'] for value, in self.conn.execute('SELECT data FROM context_parts WHERE context=? AND kind=? ORDER BY CAST(key AS INTEGER)', (identity, kind))]
        return context

    def _validate_links(self):
        if self.conn.execute('SELECT b.note FROM context_bindings b LEFT JOIN notes n ON n.path=b.note\n            WHERE n.definition IS NULL LIMIT 1').fetchone():
            raise ValueError('Indexed context refers to a missing canonical note')
        if self.conn.execute("SELECT c.target FROM context_calls c LEFT JOIN operation_context_index o\n            ON o.channel||'/'||o.name=c.target WHERE COALESCE(c.detail,'')='' AND o.identity IS NULL LIMIT 1").fetchone():
            raise ValueError('Indexed operation call has no execution context')

    def verify_sources(self, root, progress=None):
        """Reject stale maps before selected evidence can become a ready run."""
        root = Path(root).resolve()
        for number, (relative, expected) in enumerate(self.conn.execute('SELECT relative_path,hash FROM files ORDER BY path'), 1):
            path = root / relative
            if not path.resolve().is_relative_to(root) or not path.is_file() or digest(path) != expected:
                raise ValueError('Composer map is stale; source changed: ' + relative)
            if progress and number % 250 == 0:
                progress(f'Verified {number} source fingerprints; no source parsing')
        expected = self.conn.execute('SELECT count(*) FROM files').fetchone()[0]
        seen = 0
        skipped = {'ejb-jar.xml', 'web.xml', 'application.xml', 'application-client.xml', 'ra.xml', 'persistence.xml', 'beans.xml', 'faces-config.xml', 'validation.xml'}
        for path in root.rglob('*'):
            if path.is_file() and path.name.lower() not in skipped and (path.suffix.lower() in {'.java', '.xml', '.ini'} or path.name in {'.classpath', '.project'}):
                seen += 1
                if not self.conn.execute('SELECT 1 FROM files WHERE relative_path=?', (path.relative_to(root).as_posix(),)).fetchone():
                    raise ValueError('Composer map is stale; source added: ' + str(path))
        if seen != expected:
            raise ValueError('Composer map source file set changed')

    def close(self):
        if getattr(self, 'conn', None) is not None:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def __del__(self):
        self.close()

def is_indexed_map(root):
    """Probe only the small descriptor; legacy inventories stay on their existing reader."""
    path = Path(root) / 'vault-manifest.json'
    if not path.is_file() or path.stat().st_size > 65536:
        return False
    return bounded_json(path.read_text(encoding='utf-8-sig')).get('vault_schema_version') == 4

# Bundled from source/tools/composer_mapper_tools/indexed_operation_calls.py
"""Discover calls from indexed context metadata; read call-step bodies on demand only."""
import hashlib
from pathlib import Path

def iter_indexed_connections(root, analysis, progress=None):
    """Preserve the established call-graph API without opening unrelated operation notes."""
    clause = ''
    active = current_mapped()
    if active is not None and active.analysis.root == Path(root).resolve():
        analysis.conn.execute('CREATE TEMP TABLE IF NOT EXISTS requested_calls(identity TEXT PRIMARY KEY)')
        analysis.conn.executemany('INSERT OR IGNORE INTO requested_calls VALUES (?)', active.analysis.conn.execute('SELECT identity FROM selected_contexts'))
        clause = ' WHERE identity IN (SELECT identity FROM requested_calls)'
    for number, (identity, data) in enumerate(analysis.conn.execute('SELECT identity,data FROM operation_context_index' + clause + ' ORDER BY ordinal'), 1):
        context = analysis._context((identity, data))
        entry = analysis.entry(context['note'])
        operation_note = analysis.safe_path(context['note'])
        if operation_note.stat().st_size > 4 * 1024 * 1024:
            raise ValueError('Indexed operation exceeds the 4 MiB note budget')
        if hashlib.sha256(operation_note.read_bytes()).hexdigest() != entry['note_hash']:
            raise ValueError('Indexed operation note changed: ' + context['note'])
        operation = parse_operation_note(operation_note.read_text(encoding='utf-8-sig'), str(operation_note))
        key = context['channel'] + '/' + context['operation_id']
        yield ('operation', (key, dict(operation_id=context['operation_id'], channel=context['channel'], note=context['note'], source_hash=entry['source_hash'], definition_id=context['definition_id'], ref_formats=operation.ref_formats)))
        for call in context['calls']:
            note = analysis.safe_path(call['step_note'])
            if note.stat().st_size > 4 * 1024 * 1024:
                raise ValueError('Indexed call step exceeds the 4 MiB note budget')
            text = note.read_text(encoding='utf-8-sig')
            if hashlib.sha256(note.read_bytes()).hexdigest() != analysis.entry(call['step_note'])['note_hash']:
                raise ValueError('Indexed call step changed: ' + call['step_note'])
            step = parse_opstep_note(text, str(note))
            if (step.parameters.get('opExecuteName') or '') != call['target_name']:
                raise ValueError('Indexed call and source step disagree: ' + call['step_note'])
            item = dict(caller=key, callee=call.get('target_context', context['channel'] + '/' + call['target_name']), step=step.id, note=call['step_note'], parameters=step.parameters, transitions=step.transitions, evidence_hash=hashlib.sha256(text.encode()).hexdigest())
            if call.get('detail'):
                item['operation'] = item.pop('caller')
                item['detail'] = call['detail']
                yield ('issue', item)
            else:
                yield ('call', item)
        if progress and (number == 1 or number % 250 == 0):
            progress(f'Read {number} indexed operation connections')
    for item in analysis['diagnostics']:
        if item.get('kind') in {'identity', 'source_parse'}:
            yield ('issue', dict(operation=item.get('operation', ''), step=item.get('step', ''), detail=item['detail']))

def discover_indexed_calls(root, analysis, progress=None):
    """Keep the explicit complete-graph API; large exporters consume the iterator."""
    operations, calls, issues = ({}, [], [])
    for kind, value in iter_indexed_connections(root, analysis, progress):
        if kind == 'operation':
            operations[value[0]] = value[1]
        elif kind == 'call':
            calls.append(value)
        else:
            issues.append(value)
    return dict(operations=operations, calls=calls, issues=issues)

# Bundled from source/tools/operation_call_tools/indexed_waves.py
"""Calculate dependency waves and strongly connected groups with disk-backed traversal."""
import hashlib

def index_waves(conn):
    """Preserve the existing SCC/wave policy without retaining the operation graph in Python."""
    conn.executescript("CREATE TABLE links(caller TEXT,target TEXT,PRIMARY KEY(caller,target));\n        CREATE INDEX incoming_links ON links(target,caller);\n        INSERT OR IGNORE INTO links SELECT caller,callee FROM calls;\n        CREATE TABLE visited(node TEXT PRIMARY KEY);\n        CREATE TABLE stack(ordinal INTEGER PRIMARY KEY AUTOINCREMENT,node TEXT,exiting INTEGER);\n        CREATE TABLE finished(ordinal INTEGER PRIMARY KEY AUTOINCREMENT,node TEXT);\n        CREATE TABLE assigned(node TEXT PRIMARY KEY,group_id INTEGER);\n        CREATE INDEX group_members ON assigned(group_id,node);\n        CREATE TABLE groups(group_id INTEGER PRIMARY KEY,first TEXT,cycle TEXT DEFAULT '',wave INTEGER,remaining INTEGER,done INTEGER DEFAULT 0);")
    for start, in conn.execute('SELECT key FROM operations ORDER BY key'):
        if conn.execute('SELECT 1 FROM visited WHERE node=?', (start,)).fetchone():
            continue
        conn.execute('INSERT INTO stack(node,exiting) VALUES (?,0)', (start,))
        while (row := conn.execute('SELECT ordinal,node,exiting FROM stack ORDER BY ordinal DESC LIMIT 1').fetchone()):
            ordinal, node, exiting = row
            conn.execute('DELETE FROM stack WHERE ordinal=?', (ordinal,))
            if exiting:
                conn.execute('INSERT INTO finished(node) VALUES (?)', (node,))
            elif not conn.execute('SELECT 1 FROM visited WHERE node=?', (node,)).fetchone():
                conn.execute('INSERT INTO visited VALUES (?)', (node,))
                conn.execute('INSERT INTO stack(node,exiting) VALUES (?,1)', (node,))
                conn.execute('INSERT INTO stack(node,exiting) SELECT target,0 FROM links WHERE caller=? AND target NOT IN (SELECT node FROM visited) ORDER BY target DESC', (node,))
    group = 0
    for start, in conn.execute('SELECT node FROM finished ORDER BY ordinal DESC'):
        if conn.execute('SELECT 1 FROM assigned WHERE node=?', (start,)).fetchone():
            continue
        group += 1
        conn.execute('INSERT INTO assigned VALUES (?,?)', (start, group))
        conn.execute('INSERT INTO stack(node,exiting) VALUES (?,0)', (start,))
        while (row := conn.execute('SELECT ordinal,node FROM stack ORDER BY ordinal DESC LIMIT 1').fetchone()):
            ordinal, node = row
            conn.execute('DELETE FROM stack WHERE ordinal=?', (ordinal,))
            for caller, in conn.execute('SELECT caller FROM links WHERE target=? AND caller NOT IN (SELECT node FROM assigned) ORDER BY caller', (node,)):
                conn.execute('INSERT INTO assigned VALUES (?,?)', (caller, group))
                conn.execute('INSERT INTO stack(node,exiting) VALUES (?,0)', (caller,))
        conn.execute('INSERT INTO groups(group_id,first) SELECT ?,min(node) FROM assigned WHERE group_id=?', (group, group))
        cyclic = conn.execute('SELECT count(*) FROM assigned WHERE group_id=?', (group,)).fetchone()[0] > 1 or conn.execute('SELECT 1 FROM links WHERE caller=? AND target=?', (start, start)).fetchone()
        if cyclic:
            digest = hashlib.sha256()
            first = True
            for node, in conn.execute('SELECT node FROM assigned WHERE group_id=? ORDER BY node', (group,)):
                if not first:
                    digest.update(b'\n')
                digest.update(node.encode())
                first = False
            conn.execute('UPDATE groups SET cycle=? WHERE group_id=?', ('cycle-' + digest.hexdigest()[:12], group))
    conn.executescript('CREATE TABLE group_links(caller INTEGER,target INTEGER,PRIMARY KEY(caller,target));\n        CREATE INDEX group_parents ON group_links(target,caller);\n        INSERT OR IGNORE INTO group_links SELECT a.group_id,b.group_id FROM links e JOIN assigned a ON a.node=e.caller JOIN assigned b ON b.node=e.target WHERE a.group_id<>b.group_id;\n        UPDATE groups SET remaining=(SELECT count(*) FROM group_links WHERE caller=groups.group_id);\n        CREATE INDEX ready_groups ON groups(done,remaining,first);')
    while (row := conn.execute('SELECT group_id FROM groups WHERE remaining=0 AND done=0 ORDER BY first LIMIT 1').fetchone()):
        group = row[0]
        wave = conn.execute('SELECT COALESCE(max(g.wave),0)+1 FROM group_links l JOIN groups g ON g.group_id=l.target WHERE l.caller=?', (group,)).fetchone()[0]
        conn.execute('UPDATE groups SET wave=?,done=1 WHERE group_id=?', (wave, group))
        conn.execute('UPDATE groups SET remaining=remaining-1 WHERE group_id IN (SELECT caller FROM group_links WHERE target=?)', (group,))
    conn.executescript("CREATE TABLE blocked(node TEXT PRIMARY KEY);\n        INSERT INTO blocked WITH RECURSIVE reach(node) AS (SELECT i.operation FROM issues i JOIN operations o ON o.key=i.operation\n            UNION SELECT l.caller FROM links l JOIN reach r ON l.target=r.node) SELECT node FROM reach;\n        CREATE VIEW wave_rows AS SELECT o.key,o.channel,o.name,CASE WHEN b.node IS NULL THEN g.wave ELSE NULL END AS wave,g.cycle,\n            CASE WHEN b.node IS NOT NULL THEN 'Unresolved dependency' WHEN g.cycle<>'' THEN 'Cycle requires coordinated contracts' ELSE '' END AS issue,\n            (SELECT count(*) FROM links l WHERE l.caller=o.key) AS calls_count,(SELECT count(*) FROM links l WHERE l.target=o.key) AS callers_count\n            FROM operations o JOIN assigned a ON a.node=o.key JOIN groups g ON g.group_id=a.group_id LEFT JOIN blocked b ON b.node=o.key;")

# Bundled from source/tools/operation_call_tools/streamed_workbook.py
"""Write styled operation-report worksheets without retaining all workbook cells or rows."""
import math
import warnings

def streamed_sheet(workbook, name, title, context, headers, rows, widths, table_name, count, number_formats=None):
    """Stream one table while preserving the established headings, filters and cell styling."""
    from openpyxl.cell import WriteOnlyCell
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.worksheet.table import Table, TableStyleInfo
    from openpyxl.utils import get_column_letter
    sheet = workbook.create_sheet(name)
    sheet.sheet_view.showGridLines = False
    sheet.freeze_panes = 'A6'
    for column, width in enumerate(widths, 1):
        sheet.column_dimensions[get_column_letter(column)].width = width
    font = Font(name='Arial', size=11, color='243247')
    alignment = Alignment(vertical='center', wrap_text=True)
    heading = Font(name='Arial', size=11, bold=True, color='FFFFFF')
    fill = PatternFill('solid', fgColor='234568')

    def append(values, row_number, header=False):
        cells = []
        for column, value in enumerate(values, 1):
            cell = WriteOnlyCell(sheet, value=value)
            cell.font = heading if header else font
            cell.alignment = alignment
            if isinstance(value, str):
                cell.data_type = 's'
            if header:
                cell.fill = fill
                cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)
            if row_number == 2:
                cell.font = Font(name='Arial', size=16, bold=True, color='243247')
            if row_number == 3:
                cell.font = Font(name='Arial', size=10, italic=True, color='58677B')
                cell.alignment = Alignment(wrap_text=False)
            if number_formats and row_number >= 6 and (column in number_formats):
                cell.number_format = number_formats[column]
            cells.append(cell)
        sheet.append(cells)
    append([None] * len(headers), 1)
    append([title] + [None] * (len(headers) - 1), 2)
    append([context] + [None] * (len(headers) - 1), 3)
    append([None] * len(headers), 4)
    sheet.row_dimensions[5].height = 32
    append(headers, 5)
    for number, values in enumerate(rows, 6):
        lines = max((sum((max(1, math.ceil(len(line) / max(1, widths[i] - 2))) for line in str(value or '').split('\n'))) for i, value in enumerate(values)))
        sheet.row_dimensions[number].height = min(409, max(18, lines * 15))
        append(values, number)
        del sheet.row_dimensions[number]
    if not count:
        append([None] * len(headers), 6)
    table = Table(displayName=table_name, ref=f'A5:{get_column_letter(len(headers))}{max(6, 5 + count)}')
    table._initialise_columns()
    for column, label in zip(table.tableColumns, headers):
        column.name = label
    table.tableStyleInfo = TableStyleInfo(name='TableStyleMedium2', showRowStripes=True)
    with warnings.catch_warnings():
        warnings.filterwarnings('ignore', message='In write-only mode you must add table columns manually')
        sheet.add_table(table)

# Bundled from source/tools/operation_call_tools/indexed_export.py
"""Export indexed maps with SQL-backed ordering and streamed XLSX rows, without project JSON."""
from pathlib import Path
import sqlite3
import tempfile

def export_indexed_workbook(vault, output, relationships=False, progress=None):
    """Keep source map access readonly and bound traversal/workbook memory on large maps."""
    from openpyxl import Workbook
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='snapir-indexed-export-') as temporary, IndexedAnalysis(vault, progress=progress) as analysis:
        conn = sqlite3.connect(Path(temporary) / 'report.sqlite')
        try:
            conn.executescript('PRAGMA cache_size=-8192; PRAGMA temp_store=FILE;\n                CREATE TABLE operations(key TEXT PRIMARY KEY,channel TEXT,name TEXT);\n                CREATE TABLE calls(ordinal INTEGER PRIMARY KEY,caller TEXT,callee TEXT,step TEXT,note TEXT);\n                CREATE TABLE issues(ordinal INTEGER PRIMARY KEY,operation TEXT,step TEXT,detail TEXT);')
            for kind, item in iter_indexed_connections(analysis.root, analysis, progress):
                if kind == 'operation':
                    conn.execute('INSERT INTO operations VALUES (?,?,?)', (item[0], item[1]['channel'], item[1]['operation_id']))
                elif kind == 'call':
                    conn.execute('INSERT INTO calls(caller,callee,step,note) VALUES (?,?,?,?)', tuple((item[key] for key in ('caller', 'callee', 'step', 'note'))))
                else:
                    conn.execute('INSERT INTO issues(operation,step,detail) VALUES (?,?,?)', tuple((item[key] for key in ('operation', 'step', 'detail'))))
            if progress:
                progress('Calculating dependency waves with disk-backed traversal')
            index_waves(conn)
            counts = {name: conn.execute('SELECT count(*) FROM ' + name).fetchone()[0] for name in ('operations', 'calls', 'issues')}

            def plan_rows():
                for key, channel, name, wave, cycle, issue in conn.execute('SELECT key,channel,name,wave,cycle,issue FROM wave_rows ORDER BY wave IS NULL,wave,key'):
                    text = ''
                    for target, in conn.execute('SELECT target FROM links WHERE caller=? ORDER BY target', (key,)):
                        if len(text) + len(target) + 1 > 32000:
                            if not relationships:
                                raise ValueError('Excel prerequisite list exceeds a cell limit; rerun with --include-relationships')
                            text += '\n... see Relationships'
                            break
                        text += ('\n' if text else '') + target
                    yield [wave, channel, name, text or 'None', cycle or 'None', issue]
            workbook = Workbook(write_only=True)
            if progress:
                progress('Writing Excel workbook with bounded row buffers')
            streamed_sheet(workbook, 'Migration Plan', 'Operation implementation order', 'Dependencies first. Cycles require coordinated implementation; blank waves have unresolved dependencies.', ['Build wave', 'Channel', 'Operation', 'Implement after (direct)', 'Cycle group', 'Issue'], plan_rows(), [15, 18, 32, 62, 45, 45], 'MigrationPlanTable', counts['operations'], {1: '0'})
            streamed_sheet(workbook, 'Operations', 'Operation inventory', 'Counts are unique direct operation connections, not step counts or implementation effort.', ['Channel', 'Operation', 'Calls count', 'Callers count', 'Build wave', 'Cycle group'], conn.execute("SELECT channel,name,calls_count,callers_count,wave,CASE WHEN cycle='' THEN 'None' ELSE cycle END FROM wave_rows ORDER BY key"), [18, 32, 17, 17, 16, 45], 'OperationsTable', counts['operations'], {3: '#,##0', 4: '#,##0', 5: '#,##0'})
            if relationships:
                streamed_sheet(workbook, 'Relationships', 'Operation call evidence', 'Filter Caller or Called operation. Multiple call sites are retained as evidence.', ['Caller', 'Called operation', 'Invoking step', 'Mapper note'], conn.execute('SELECT caller,callee,step,note FROM calls ORDER BY ordinal'), [42, 42, 32, 62], 'RelationshipsTable', counts['calls'])
            if counts['issues']:
                streamed_sheet(workbook, 'Issues', 'Unresolved operation relationships', 'Affected operations and their callers have no assigned build wave.', ['Operation', 'Step', 'Issue'], conn.execute('SELECT operation,step,detail FROM issues ORDER BY ordinal'), [42, 45, 90], 'IssuesTable', counts['issues'])
            staging = output.with_name(output.name + '.tmp')
            try:
                workbook.save(staging)
                staging.replace(output)
            finally:
                staging.unlink(missing_ok=True)
            return counts
        finally:
            conn.close()

# Bundled from source/tools/composer_mapper_tools/vault_manifest.py
"""Validate scoped vault identity and enumerate notes without guessing folder depth."""
import hashlib
import codecs
import re
from pathlib import Path

def _read_note_metadata(candidate):
    """Hash and validate UTF-8 in one buffered read, retaining only the frontmatter."""
    digest = hashlib.sha256()
    decoder = codecs.getincrementaldecoder('utf-8-sig')()
    header, metadata = ('', None)
    with candidate.open('rb') as note:
        while (chunk := note.read(65536)):
            digest.update(chunk)
            text = decoder.decode(chunk)
            if metadata is None:
                header += text
                match = re.search('(?s)(?:^|\\n)---\\r?\\n.*?\\r?\\n---\\r?\\n', header)
                if match:
                    metadata = parse_frontmatter(header[:match.end()].replace('\r\n', '\n').replace('\r', '\n'))
                    header = ''
        tail = decoder.decode(b'', final=True)
    if metadata is None:
        metadata = parse_frontmatter((header + tail).replace('\r\n', '\n').replace('\r', '\n'))
    return (metadata, digest.hexdigest())

def read_vault_manifest(vault, *, retain_inventory=True, progress=None, allow_shared=False):
    """Return a validated manifest, or None for a legacy vault.

    Shared schema-three notes require explicit opt-in; converter readers stay schema two.

    Incomplete generation, unknown schemas, conflicting views and escaped paths are errors.
    Exporters can discard non-operation records after validation with retain_inventory=False.
    Compact identity indexes remain in memory; JSON and note bodies are read incrementally.
    Other callers retain the full manifest by default. Progress callbacks receive text only.
    This reader uses only Python's standard library so standalone exporters can bundle it.
    """
    root = Path(vault).resolve()
    from tools.composer_mapper_tools.indexed_analysis import is_indexed_map, IndexedAnalysis
    if is_indexed_map(root):
        return IndexedAnalysis(root, progress=progress)
    path = root / 'vault-manifest.json'
    if (root / 'vault-generation.json').exists():
        raise ValueError('Incomplete scoped vault generation: ' + str(root))
    if not path.exists():
        if (root / 'channels').exists() and list((root / 'channels').glob('*/operations/*/operation.md')):
            raise ValueError('Scoped vault is missing vault-manifest.json')
        return None
    manifest = {}
    paths, usages, definitions = ({}, set(), {})
    operations = []
    processed = 0
    for field, event, entry in iter_manifest_fields(path):
        if event == 'array':
            manifest[field] = []
            continue
        if event == 'value':
            if field == 'vault_schema_version' and entry == 3 and (not allow_shared):
                raise ValueError('Shared schema-three vault requires an updated consumer; converter support is not implemented')
            manifest[field] = entry
            continue
        if field != 'entities':
            manifest[field].append(entry)
            continue
        processed += 1
        required = ('kind', 'entity_id', 'definition_id', 'usage_id', 'note', 'source_relative_path', 'source_selector', 'source_hash', 'note_hash')
        if not isinstance(entry, dict) or any((not isinstance(entry.get(key), str) or not entry[key] for key in required)):
            raise ValueError('Invalid scoped entity identity')
        relative = entry['note']
        candidate = (root / relative).resolve()
        if '\\' in relative or Path(relative).is_absolute() or (not candidate.is_relative_to(root)) or (not candidate.is_file()):
            raise ValueError('Missing or unsafe scoped note path: ' + relative)
        if relative.casefold() in paths or entry['usage_id'] in usages:
            raise ValueError('Duplicate scoped note path or usage identity: ' + relative)
        metadata, note_hash = _read_note_metadata(candidate)
        if note_hash != entry['note_hash']:
            raise ValueError('Scoped note differs from completed manifest: ' + relative)
        for field, key in (('entity_id', 'entity_id'), ('qualified_entity_id', 'definition_id'), ('usage_id', 'usage_id')):
            if str(metadata.get(field, '')) != entry[key]:
                raise ValueError('Scoped note and manifest identity disagree: ' + relative)
        if str(metadata.get('operation_identity') or '') != entry.get('operation_identity', ''):
            raise ValueError('Scoped note belongs to another operation view: ' + relative)
        coordinates = tuple((entry[key] for key in ('kind', 'entity_id', 'source_relative_path', 'source_selector', 'source_hash')))
        previous = definitions.setdefault(entry['definition_id'], coordinates)
        if previous != coordinates:
            raise ValueError('Conflicting views of source definition: ' + entry['definition_id'])
        paths[relative.casefold()] = entry.get('operation_identity')
        usages.add(entry['usage_id'])
        if retain_inventory or (entry['kind'] == 'operation' and entry.get('operation_id')):
            manifest['entities'].append(entry)
        if progress and (processed == 1 or processed % 250 == 0):
            progress(f'Validated {processed} notes: {relative}')
        if entry['kind'] != 'operation' or not entry.get('operation_id'):
            continue
        if entry['operation_id'] != entry['entity_id'] or not entry.get('channel') or (not entry.get('operation_identity')):
            raise ValueError('Invalid effective operation identity: ' + entry['note'])
        if str(metadata.get('channel', '')) != entry['channel']:
            raise ValueError('Scoped operation channel and manifest disagree: ' + entry['note'])
        operations.append(entry)
    if manifest.get('vault_schema_version') not in (2, 3) or manifest.get('identity_version') != 1:
        raise ValueError('Unsupported vault schema or identity version')
    shared = manifest['vault_schema_version'] == 3
    if shared and (not allow_shared):
        raise ValueError('Shared schema-three vault requires an updated consumer; converter support is not implemented')
    if manifest.get('complete') is not True or not manifest.get('workspace_id'):
        raise ValueError('Incomplete scoped vault manifest')
    if not isinstance(manifest.get('entities'), list):
        raise ValueError('Missing scoped entity inventory')
    if progress:
        progress(f'Finalizing validation after checking {processed} notes; checking operation references and connections')
    for entry in operations:
        for reference in entry.get('references', {}).values():
            if reference.casefold() not in paths or (not shared and paths[reference.casefold()] != entry['operation_identity']):
                raise ValueError('Reference escapes owning operation view: ' + reference)
    if shared:
        _validate_operation_contexts(manifest, paths, operations)
    if progress:
        progress(f'Validated {processed} notes; {len(operations)} effective operations')
    return manifest

def operation_note_paths(vault, manifest=None, *, manifest_validated=False):
    """Enumerate effective operation notes from a scoped manifest or legacy folders."""
    root = Path(vault).resolve()
    manifest = read_vault_manifest(root) if manifest is None and (not manifest_validated) else manifest
    if manifest is not None:
        return [root / entry['note'] for entry in manifest['entities'] if entry['kind'] == 'operation' and entry.get('operation_id')]
    if not (root / 'operations').is_dir():
        raise ValueError('Missing operations folder: ' + str(root))
    return sorted((root / 'operations').rglob('*.md'))

def _validate_operation_contexts(manifest, paths, operations):
    """Validate contextual connections against canonical notes and resolved call targets."""
    contexts = manifest.get('operation_contexts')
    if not isinstance(contexts, list):
        raise ValueError('Missing consuming-channel operation connections')
    definitions = {entry['definition_id']: entry for entry in operations}
    by_key = {}
    for context in contexts:
        if not isinstance(context, dict) or any((not isinstance(context.get(key), str) or not context[key] for key in ('channel', 'operation_id', 'operation_identity', 'definition_id', 'note'))):
            raise ValueError('Invalid operation connection identity')
        key = context['channel'] + '/' + context['operation_id']
        if key in by_key:
            raise ValueError('Duplicate consuming-channel operation connection: ' + key)
        by_key[key] = context
        definition = definitions.get(context['definition_id'])
        if definition is None or definition['note'] != context['note'] or definition['entity_id'] != context['operation_id']:
            raise ValueError('Connection refers to an invalid canonical operation: ' + key)
        references = context.get('references')
        steps = context.get('step_notes')
        if not isinstance(references, dict) or not isinstance(steps, list):
            raise ValueError('Missing resolved dependencies: ' + key)
        if references.get('operations:' + context['operation_id']) != context['note']:
            raise ValueError('Invalid contextual operation reference: ' + key)
        for note in [*references.values(), *steps]:
            if not isinstance(note, str) or note.casefold() not in paths:
                raise ValueError('Missing canonical dependency note: ' + str(note))
        for note in steps:
            if paths[note.casefold()] != definition['operation_identity']:
                raise ValueError('Context step belongs to another source operation: ' + note)
        if context.get('entry_step_note', '') != (steps[0] if steps else ''):
            raise ValueError('Invalid contextual entry step: ' + key)
        transitions = context.get('transition_targets')
        if not isinstance(transitions, dict) or any((note not in steps or not isinstance(targets, dict) or any((target not in steps for target in targets.values())) for note, targets in transitions.items())):
            raise ValueError('Invalid contextual transition targets: ' + key)
        if not isinstance(context.get('calls'), list):
            raise ValueError('Missing contextual operation calls: ' + key)
    for key, context in by_key.items():
        for call in context['calls']:
            if not isinstance(call, dict) or call.get('step_note') not in context['step_notes']:
                raise ValueError('Invalid contextual call step: ' + key)
            if call.get('detail'):
                continue
            target = by_key.get(call.get('target_context'))
            if target is None or target['channel'] != context['channel'] or target['note'] != call.get('target_note') or (target['definition_id'] != call.get('target_definition_id')) or (target['operation_id'] != call.get('target_name')):
                raise ValueError('Invalid resolved operation call: ' + key)

# Bundled from source/tools/operation_call_tools/discovery.py
"""Resolve CCComplexOpStep targets from Composer Mapper Markdown evidence."""
import hashlib
import re
from pathlib import Path
from urllib.parse import unquote
COMPLEX_CLASS = 'com.ibm.il.dse.cc.cut.CCComplexOpStep'
_UNREAD_MANIFEST = object()

def _links(section):
    """Keep URI escapes until resolution; percent signs in wiki filenames are literal."""
    return [match[0] or match[1].split('|', 1)[0].replace('%', '%25') for match in re.findall('\\[[^\\]]*\\]\\(([^)]+)\\)|\\[\\[([^\\]]+)\\]\\]', section)]

def _note_path(root, owner, target):
    """Try literal hash filenames, then strip a URI fragment before decoding once."""
    for destination in (target, target.split('#', 1)[0]):
        note = unquote(destination)
        if not note.endswith('.md'):
            note += '.md'
        for candidate in (root / note, owner.parent / note):
            path = candidate.resolve()
            if path.is_relative_to(root) and path.is_file():
                return path
    raise ValueError('Missing linked step note: ' + target)

def _missing_target_detail(channel, name, operations):
    """Explain a missing implicit-base view without redirecting to a different channel view."""
    callee = channel + '/' + name
    base = 'XML/' + name
    if channel.upper() != 'XML' and base in operations:
        return 'Missing inherited XML-base operation view: ' + callee + '; ' + base + ' exists, but its caller-channel view is absent. Regenerate the vault with a Mapper that includes the implicit XML base and local overrides.'
    return 'Target is missing in caller channel: ' + callee + '; cross-channel targets require explicit resolution'

def discover_operation_calls(vault, *, progress=None, validated_manifest=_UNREAD_MANIFEST):
    """Read a vault without mutation; return channel-qualified operations, calls and issues."""
    root = Path(vault).resolve()
    manifest = read_vault_manifest(root, retain_inventory=False, progress=progress, allow_shared=True) if validated_manifest is _UNREAD_MANIFEST else validated_manifest
    if manifest is not None and manifest.get('vault_schema_version') == 4:
        from tools.composer_mapper_tools.indexed_operation_calls import discover_indexed_calls
        try:
            return discover_indexed_calls(root, manifest, progress)
        finally:
            if validated_manifest is _UNREAD_MANIFEST:
                manifest.close()
    if manifest is not None and manifest.get('vault_schema_version') == 3:
        return _discover_context_calls(root, manifest, progress)
    note_paths = operation_note_paths(root, manifest, manifest_validated=True)
    registry = parse_channel_operation_registry(str(root / 'analysis/channel-operation-registry.md'))
    operations, calls, issues = ({}, [], [])
    if manifest is not None:
        issues.extend((dict(operation=item.get('operation', ''), step=item.get('step', ''), detail=item['detail']) for item in manifest.get('diagnostics', []) if item.get('kind') in {'identity', 'source_parse'}))
    documents = []
    for number, path in enumerate(note_paths, 1):
        if progress:
            progress(f'Reading operation {number}/{len(note_paths)}: {path.relative_to(root)}')
        text = path.read_text(encoding='utf-8-sig')
        op = parse_operation_note(text, str(path))
        channels = {op.channel} if op.channel else {channel for name, channel, _ in registry if name == op.id}
        if not op.id or not channels:
            issues.append(dict(operation=str(path.relative_to(root)), step='', detail='Operation ID or channel is missing'))
            continue
        for channel in sorted(channels):
            key = channel + '/' + op.id
            if key in operations:
                issues.append(dict(operation=key, step='', detail='Duplicate operation identity'))
                continue
            operations[key] = dict(operation_id=op.id, channel=channel, note=str(path.relative_to(root)), source_hash=op.source_hash, ref_formats=op.ref_formats)
            documents.append((key, op, path, text))
    for number, (caller, op, path, text) in enumerate(documents, 1):
        if progress:
            progress(f'Resolving calls {number}/{len(documents)}: {caller}')
        targets = _links(parse_section(text, 'Steps'))
        if op.steps and (not targets):
            issues.append(dict(operation=caller, step='', detail='Steps have no resolvable Markdown links'))
        for target in targets:
            try:
                step_path = _note_path(root, path, target)
                step_text = step_path.read_text(encoding='utf-8-sig')
                step = parse_opstep_note(step_text, str(step_path))
                raw = parse_key_value_bullets(parse_section(step_text, 'Raw Attributes'))
                impl = raw.get('implClass') or step.impl_class or ''
                if impl != COMPLEX_CLASS and (not impl.endswith('|' + COMPLEX_CLASS + ']]')):
                    continue
                channel = caller.split('/', 1)[0]
                if step.only_for and channel.upper() not in re.split('[,;\\s]+', step.only_for.strip().upper()):
                    continue
                if step.parent_operation_id and step.parent_operation_id != op.id:
                    raise ValueError('Linked step belongs to another operation; possible Mapper step-ID collision')
                name = step.parameters.get('opExecuteName') or raw.get('opExecuteName')
                if not name:
                    raise ValueError('CCComplexOpStep has no opExecuteName')
                callee = channel + '/' + name
                if callee not in operations:
                    issues.append(dict(operation=caller, step=step.id, callee=callee, note=str(step_path.relative_to(root)), parameters=step.parameters, transitions=step.transitions, evidence_hash=hashlib.sha256(step_text.encode()).hexdigest(), detail=_missing_target_detail(channel, name, operations)))
                    continue
                calls.append(dict(caller=caller, callee=callee, step=step.id, note=str(step_path.relative_to(root)), parameters=step.parameters, transitions=step.transitions, evidence_hash=hashlib.sha256(step_text.encode()).hexdigest()))
            except (OSError, ValueError) as exc:
                issues.append(dict(operation=caller, step=target, detail=str(exc)))
    return dict(operations=operations, calls=calls, issues=issues)

def _discover_context_calls(root, manifest, progress):
    """Read reachable runtime connections while reusing their canonical source notes."""
    operations, calls = ({}, [])
    issues = [dict(operation=item.get('operation', ''), step=item.get('step', ''), detail=item['detail']) for item in manifest.get('diagnostics', []) if item.get('kind') in {'identity', 'source_parse'}]
    documents, steps = ({}, {})
    for number, context in enumerate(manifest['operation_contexts'], 1):
        key = context['channel'] + '/' + context['operation_id']
        if progress:
            progress(f'Reading operation connections {number}: {key}')
        note = context['note']
        if note not in documents:
            documents[note] = parse_operation_note((root / note).read_text(encoding='utf-8-sig'), str(root / note))
        op = documents[note]
        operations[key] = dict(operation_id=op.id, channel=context['channel'], note=note, source_hash=op.source_hash, ref_formats=op.ref_formats, definition_id=context['definition_id'])
        for call in context['calls']:
            step_note = call['step_note']
            if step_note not in steps:
                text = (root / step_note).read_text(encoding='utf-8-sig')
                steps[step_note] = (parse_opstep_note(text, str(root / step_note)), hashlib.sha256(text.encode()).hexdigest())
            step, evidence = steps[step_note]
            if step.parent_operation_id and step.parent_operation_id != op.id:
                raise ValueError('Context call step belongs to another source operation: ' + step_note)
            if (step.parameters.get('opExecuteName') or '') != call['target_name']:
                raise ValueError('Context call target disagrees with source step: ' + step_note)
            item = dict(caller=key, callee=call.get('target_context', context['channel'] + '/' + call['target_name']), step=step.id, note=step_note, parameters=step.parameters, transitions=step.transitions, evidence_hash=evidence)
            if call.get('detail'):
                item['operation'] = item.pop('caller')
                item['detail'] = call['detail']
                issues.append(item)
            else:
                calls.append(item)
    return dict(operations=operations, calls=calls, issues=issues)

# Bundled from source/tools/operation_call_tools/ordering.py
"""Calculate dependency-first waves with explicit strongly connected groups."""
import heapq
import hashlib

def operation_waves(graph):
    """Return deterministic SCC groups and waves without recursion limits on large vaults."""
    edges = {key: set() for key in graph['operations']}
    reverse = {key: set() for key in edges}
    for call in graph['calls']:
        edges[call['caller']].add(call['callee'])
        reverse[call['callee']].add(call['caller'])
    seen, finished = (set(), [])
    for start in sorted(edges):
        if start in seen:
            continue
        stack = [(start, False)]
        while stack:
            node, exiting = stack.pop()
            if exiting:
                finished.append(node)
            elif node not in seen:
                seen.add(node)
                stack.append((node, True))
                stack.extend(((other, False) for other in sorted(edges[node], reverse=True) if other not in seen))
    groups, assigned = ([], {})
    for start in reversed(finished):
        if start in assigned:
            continue
        group, pending = ([], [start])
        index = len(groups)
        assigned[start] = index
        while pending:
            node = pending.pop()
            group.append(node)
            for other in reverse[node]:
                if other not in assigned:
                    assigned[other] = index
                    pending.append(other)
        groups.append(sorted(group))
    dependencies = {i: {assigned[target] for node in nodes for target in edges[node] if assigned[target] != i} for i, nodes in enumerate(groups)}
    dependents = {i: set() for i in dependencies}
    for i, targets in dependencies.items():
        for target in targets:
            dependents[target].add(i)
    remaining = {i: len(targets) for i, targets in dependencies.items()}
    ready = [(groups[i][0], i) for i, count in remaining.items() if not count]
    heapq.heapify(ready)
    waves = {}
    while ready:
        _, i = heapq.heappop(ready)
        waves[i] = 1 + max((waves[target] for target in dependencies[i]), default=0)
        for parent in dependents[i]:
            remaining[parent] -= 1
            if remaining[parent] == 0:
                heapq.heappush(ready, (groups[parent][0], parent))
    blocked = {issue['operation'] for issue in graph['issues'] if issue['operation'] in edges}
    cyclic = {node for nodes in groups for node in nodes if len(nodes) > 1 or node in edges[node]}
    cycle_ids = {i: 'cycle-' + hashlib.sha256('\n'.join(nodes).encode()).hexdigest()[:12] for i, nodes in enumerate(groups) if any((node in cyclic for node in nodes))}
    pending = list(blocked)
    while pending:
        for parent in reverse[pending.pop()]:
            if parent not in blocked:
                blocked.add(parent)
                pending.append(parent)
    return {node: dict(wave=None if node in blocked else waves[assigned[node]], cycle_group=cycle_ids.get(assigned[node], ''), prerequisites=sorted(edges[node]), calls_count=len(edges[node]), callers_count=len(reverse[node]), issue='Unresolved dependency' if node in blocked else 'Cycle requires coordinated contracts' if node in cyclic else '') for node in sorted(edges)}

def ordered_operations(graph, selected, available=()):
    """Order selected operations; reject unresolved targets, cycles and omitted prerequisites."""
    waves = operation_waves(graph)
    selected = set(selected)
    for node in sorted(selected):
        if node not in waves:
            raise ValueError('Operation is missing from mapped call graph: ' + node)
        item = waves[node]
        if item['issue']:
            raise ValueError(node + ': ' + item['issue'])
        missing = set(item['prerequisites']) - selected - set(available)
        if missing:
            raise ValueError(node + ': include prerequisite operations: ' + ', '.join(sorted(missing)))
    return sorted(selected, key=lambda node: (waves[node]['wave'], node))

# Standalone readers use the same function bodies, including their lazy imports.
import types
def current_mapped(workspace=None):
    return None
import importlib.util
try:
    _standalone = importlib.util.find_spec("tools.composer_mapper_tools") is None
except (ModuleNotFoundError, ValueError):
    _standalone = True
if _standalone:
    for _module_name, _exports in {'tools.composer_mapper_tools.frontmatter_parser': ['parse_frontmatter', 'parse_section', '_parse_yaml_subset', '_coerce_scalar', 'clean_markdown_value', 'parse_bullet_values', 'parse_key_value_bullets'], 'tools.composer_mapper_tools.operation_parser': ['parse_operation_note', '_first_bullet', '_strip_step_suffix'], 'tools.composer_mapper_tools.opstep_parser': ['parse_opstep_note', '_parse_impl_class', '_parse_transitions', '_parse_return_body_switches', '_first'], 'tools.composer_mapper_tools.channel_registry_parser': ['parse_channel_operation_registry'], 'tools.composer_mapper_tools.manifest_json_stream': ['_ManifestJsonReader', 'iter_manifest_fields'], 'tools.operation_call_tools.export_progress': ['ExportProgress'], 'tools.composer_mapper_tools.indexed_analysis': ['bounded_json', 'SqlSequence', 'digest', 'IndexedAnalysis', 'is_indexed_map'], 'tools.composer_mapper_tools.indexed_operation_calls': ['iter_indexed_connections', 'discover_indexed_calls'], 'tools.operation_call_tools.indexed_waves': ['index_waves'], 'tools.operation_call_tools.streamed_workbook': ['streamed_sheet'], 'tools.operation_call_tools.indexed_export': ['export_indexed_workbook'], 'tools.composer_mapper_tools.vault_manifest': ['_read_note_metadata', 'read_vault_manifest', 'operation_note_paths', '_validate_operation_contexts'], 'tools.operation_call_tools.discovery': ['_links', '_note_path', '_missing_target_detail', 'discover_operation_calls', '_discover_context_calls'], 'tools.operation_call_tools.ordering': ['operation_waves', 'ordered_operations'], 'tools.composer_mapper_tools.mapped_scope': ['current_mapped']}.items():
        _module = types.ModuleType(_module_name)
        _module.__dict__.update({name: globals()[name] for name in _exports})
        sys.modules[_module_name] = _module

if __name__ == '__main__':
    raise SystemExit(main())
