"""Select a mapped operation closure and adapt its facts to existing inventory contracts."""

from collections.abc import Mapping
from pathlib import Path
from types import SimpleNamespace
from copy import copy

from models.source_component_identity import SourceImplementationRecord
from tools.component_inventory_tools.identity import stable_id
from tools.component_inventory_tools.mapped_definitions import MappedDefinitions


class ClassLocations(Mapping):
    """Iterate selected classes; resolve names against the complete declaration index."""

    def __init__(self, mapped):
        self.mapped, self.conn = mapped, mapped.analysis.conn

    def __iter__(self):
        return (row[0] for row in self.conn.execute('SELECT DISTINCT s.fqcn FROM java_sources s JOIN selected_java j ON s.file=j.file ORDER BY s.fqcn'))

    def __len__(self):
        return self.conn.execute('SELECT count(DISTINCT s.fqcn) FROM java_sources s JOIN selected_java j ON s.file=j.file').fetchone()[0]

    def __contains__(self, key):
        return self.conn.execute('SELECT 1 FROM java_sources WHERE fqcn=? LIMIT 1', (key,)).fetchone() is not None

    def __getitem__(self, key):
        values=[];weight=0
        for row in self.conn.execute('SELECT file FROM java_sources WHERE fqcn=? ORDER BY file LIMIT 10001',(key,)):
            value=self.mapped.location(row[0]);weight+=len(value)*2+64
            if weight>4*1024*1024:raise ValueError('Java candidate metadata exceeds the 4 MiB lookup budget: '+key)
            values.append(value)
        if len(values) > 10000:
            raise ValueError('Excessive duplicate Java declarations: ' + key)
        if not values:
            raise KeyError(key)
        return values


class ClassProjects(Mapping):
    """Project ownership by exact file, without retaining every declaration in Python."""

    def __init__(self, mapped, *, selected_only=False):
        self.mapped = mapped
        self.selected_only = selected_only

    def __getitem__(self, path):
        original = str(self.mapped.analysis.source_root / Path(path).relative_to(self.mapped.workspace))
        row = self.mapped.analysis.conn.execute('SELECT project FROM java_sources WHERE file=?', (original,)).fetchone()
        if row is None:
            raise KeyError(path)
        return row[0]

    def __iter__(self):
        query = 'SELECT s.file FROM java_sources s' + (' JOIN selected_java j ON j.file=s.file' if self.selected_only else '') + ' ORDER BY s.file'
        return (self.mapped.location(row[0]) for row in self.mapped.analysis.conn.execute(query))

    def __len__(self):
        query = 'SELECT count(*) FROM java_sources s' + (' JOIN selected_java j ON j.file=s.file' if self.selected_only else '')
        return self.mapped.analysis.conn.execute(query).fetchone()[0]


class MappedSourceIndex(SimpleNamespace):
    """Support existing scoped projections without converting the global SQL index to a dict."""
    def model_copy(self, *, update=None):
        result = copy(self)
        result.__dict__.update(update or {})
        return result


class MappedInventory:
    """Own one selected overlay; global facts remain readonly in the reusable map."""

    def __init__(self, analysis, workspace, config):
        self.analysis, self.workspace, self.config = analysis, Path(workspace).resolve(), config
        conn = analysis.conn
        conn.executescript('DROP TABLE IF EXISTS temp.selected_contexts; DROP TABLE IF EXISTS temp.selected_java; DROP TABLE IF EXISTS temp.selected_definitions;')
        conn.execute('CREATE TEMP TABLE selected_contexts(identity TEXT PRIMARY KEY,selected INTEGER)')
        for channel in config.target_channels:
            for identity, name in conn.execute('SELECT identity,name FROM operation_context_index WHERE channel=? ORDER BY ordinal', (channel,)):
                if (not config.include_operations or name in config.include_operations) and name not in (config.exclude_operations or []):
                    conn.execute('INSERT OR IGNORE INTO selected_contexts VALUES (?,1)', (identity,))
        if not conn.execute('SELECT 1 FROM selected_contexts LIMIT 1').fetchone():
            raise ValueError('No requested operation execution context exists in the indexed map')
        conn.execute('''INSERT OR IGNORE INTO selected_contexts WITH RECURSIVE reach(identity) AS (
            SELECT identity FROM selected_contexts UNION SELECT o.identity FROM context_calls c JOIN reach r ON c.context=r.identity
            JOIN operation_context_index o ON o.channel||'/'||o.name=c.target WHERE COALESCE(c.detail,'')='') SELECT identity,0 FROM reach''')
        conn.execute('CREATE TEMP TABLE selected_java(file TEXT PRIMARY KEY)')
        conn.execute('''INSERT INTO selected_java WITH RECURSIVE roots(file) AS (
            SELECT r.file FROM context_java_roots r JOIN selected_contexts s ON s.identity=r.context
            UNION SELECT e.target FROM java_edges e JOIN roots r ON e.caller=r.file) SELECT file FROM roots''')
        self.definitions = MappedDefinitions(analysis, self.workspace)
        roots, references = {}, {}
        for project, root in conn.execute('SELECT project,root FROM java_roots ORDER BY project,root'):
            roots.setdefault(project, []).append(self.location(root))
        for project, target in conn.execute('SELECT project,target FROM java_project_refs ORDER BY project,target'):
            references.setdefault(project, []).append(target)
        for (name,) in conn.execute('SELECT name FROM java_projects WHERE declared=1'):
            references.setdefault(name, [])
        issues = [row[0] for row in conn.execute("SELECT json_extract(data,'$.message') FROM records WHERE collection='source_issues' LIMIT 10001")]
        self.index = MappedSourceIndex(classes=ClassLocations(self), class_projects=ClassProjects(self), source_roots=roots,
                                     project_references=references, issues=issues, workspace_root=str(self.workspace))

    def location(self, original):
        return str(self.workspace / Path(original).relative_to(self.analysis.source_root))

    def is_selected(self, path):
        """Keep unrelated duplicate-FQCN candidates as lookup metadata, not loaded implementations."""
        original=str(self.analysis.source_root/Path(path).relative_to(self.workspace))
        return self.analysis.conn.execute('SELECT 1 FROM selected_java WHERE file=?',(original,)).fetchone() is not None

    def implementation(self, path, fqcn, workspace_id):
        original = str(self.analysis.source_root / Path(path).relative_to(self.workspace))
        row = self.analysis.conn.execute('SELECT s.root,f.relative_path,f.hash FROM java_sources s JOIN files f ON f.path=s.file WHERE s.file=?', (original,)).fetchone()
        relative_root = Path(row[0]).relative_to(self.analysis.source_root).as_posix()
        package, _, name = fqcn.rpartition('.')
        return SourceImplementationRecord(implementation_id=stable_id(workspace_id, relative_root, row[1], fqcn, None),
            workspace_id=workspace_id, source_root=relative_root, source_path=row[1], package_name=package,
            class_name=name, source_hash=row[2])

    def mappings(self):
        values, scopes = {}, {}
        for channel, tag, fqcn, source, origin, group in self.analysis.conn.execute('SELECT * FROM context_mappings ORDER BY channel,tag'):
            values.setdefault(channel, {})[tag] = dict(fqcn=fqcn, source=source, origin_channel=origin, group=group)
        for channel, target in self.analysis.conn.execute('SELECT channel,target FROM context_imports ORDER BY channel,target'):
            scopes.setdefault(channel, []).append(target)
        issues=(row[0] for row in self.analysis.conn.execute("SELECT json_extract(data,'$.message') FROM records WHERE collection IN ('component_issues','dependency_issues','java_issues') ORDER BY ordinal"))
        return values, issues, scopes

    def operation_nodes(self, operation, root):
        """Walk active step subtrees while preserving canonical XML bodies and selectors."""
        from tools.conversion_tools.channel_filter_tool import _is_allowed_for_channel
        from tools.component_inventory_tools.xml_documents import tag_name
        def nodes(node):
            if tag_name(node)=='opStep' and not _is_allowed_for_channel(node.get('onlyFor'),operation['channel']):
                return
            yield node
            for child in node:
                yield from nodes(child)
        return nodes(root)
