"""Load selected XML definitions from normalized mapper rows, without parsing source XML."""

from pathlib import Path
from xml.etree import ElementTree

from tools.component_inventory_tools.xml_documents import walk_nodes

MAX_DEFINITION_BYTES = 4 * 1024 * 1024


class MappedDefinitions:
    """Use metadata to resolve candidates before hydrating one bounded definition."""

    def __init__(self, analysis, workspace):
        self.analysis, self.conn, self.workspace = analysis, analysis.conn, Path(workspace)
        self.conn.execute('CREATE TEMP TABLE selected_definitions(node TEXT PRIMARY KEY,visited INTEGER DEFAULT 0)')
        self.conn.execute('CREATE INDEX temp.selected_definition_work ON selected_definitions(visited,node)')
        self.conn.execute('''INSERT INTO selected_definitions(node) SELECT DISTINCT d.node FROM canonical_definitions d
            JOIN files f ON f.path=d.file JOIN notes n ON n.source_relative_path=f.relative_path AND n.source_selector=d.selector
            JOIN operation_context_index o ON o.definition=n.definition JOIN selected_contexts s ON s.identity=o.identity
            WHERE d.kind='operation' ''')
        self.conn.execute("""INSERT OR IGNORE INTO selected_definitions(node) SELECT d.node
            FROM context_bindings b JOIN selected_contexts s ON s.identity=b.context JOIN notes n ON n.path=b.note
            JOIN files f ON f.relative_path=n.source_relative_path JOIN canonical_definitions d
            ON d.file=f.path AND d.selector=n.source_selector WHERE n.kind IN ('format','context')""")
        # Inline occurrences belong to the selected XML subtree too.
        self.conn.execute('''INSERT OR IGNORE INTO selected_definitions(node) WITH RECURSIVE children(id) AS (
            SELECT node FROM selected_definitions UNION SELECT n.id FROM xml_nodes n JOIN children c ON n.parent=c.id)
            SELECT d.node FROM canonical_definitions d JOIN children c ON c.id=d.node''')

    def metadata(self, node):
        row = self.conn.execute('''SELECT d.node,d.kind,d.name,d.file,d.channel,d.selector,f.relative_path
            FROM canonical_definitions d JOIN files f ON f.path=d.file WHERE d.node=?''', (node,)).fetchone()
        return dict(node_id=row[0], kind=row[1], logical_id=row[2], original_file=row[3], channel=row[4], selector=row[5], path=self.workspace / row[6])

    def hydrate(self, value):
        root = None
        stack = []
        weight = 0
        inherited = {'xml':'http://www.w3.org/XML/1998/namespace'}
        for name, namespace in self.conn.execute('''WITH RECURSIVE parents(id,parent,depth) AS (
            SELECT p.id,p.parent,1 FROM xml_nodes n JOIN xml_nodes p ON p.id=n.parent WHERE n.id=?
            UNION ALL SELECT n.id,n.parent,p.depth+1 FROM xml_nodes n JOIN parents p ON n.id=p.parent)
            SELECT a.name,a.value FROM parents p JOIN xml_attributes a ON a.node=p.id
            WHERE a.name='xmlns' OR a.name LIKE 'xmlns:%' ORDER BY p.depth DESC''', (value['node_id'],)):
            inherited[name.partition(':')[2]] = namespace

        def expanded(name, namespaces, attribute=False):
            prefix, separator, local = name.partition(':')
            if separator:
                if prefix not in namespaces:
                    raise ValueError('Unbound XML namespace prefix: '+prefix)
                return '{'+namespaces[prefix]+'}'+local
            namespace = namespaces.get('') if not attribute else None
            return '{'+namespace+'}'+name if namespace else name
        rows = self.conn.execute('''WITH RECURSIVE children(id) AS (SELECT ? UNION ALL SELECT n.id FROM xml_nodes n
            JOIN children c ON n.parent=c.id) SELECT n.id,n.parent,n.type,n.name,n.value FROM xml_nodes n
            JOIN children c ON c.id=n.id ORDER BY n.rowid''', (value['node_id'],))
        by_id = {}
        last_child = {}
        for identity, parent, node_type, tag, text in rows:
            weight += len(tag or '') + len(text or '')
            if weight * 4 > MAX_DEFINITION_BYTES or len(by_id) > 50000:
                raise ValueError('Selected XML definition exceeds the 4 MiB materialization budget: ' + str(value['path']) + value['selector'])
            if node_type == 1:
                attributes = dict(self.conn.execute('SELECT name,value FROM xml_attributes WHERE node=? ORDER BY rowid', (identity,)))
                weight += sum(len(key) + len(item) for key, item in attributes.items())
                if weight*4>MAX_DEFINITION_BYTES:
                    raise ValueError('Selected XML attributes exceed the materialization budget: '+str(value['path']))
                while stack and stack[-1][0] != parent:
                    stack.pop()
                namespaces = stack[-1][1] if stack else inherited
                declarations = {name.partition(':')[2]:namespace for name,namespace in attributes.items() if name=='xmlns' or name.startswith('xmlns:')}
                if declarations:
                    namespaces = dict(namespaces,**declarations)
                attributes = {expanded(name,namespaces,True):item for name,item in attributes.items() if name!='xmlns' and not name.startswith('xmlns:')}
                element = ElementTree.Element(expanded(tag,namespaces), attributes)
                stack.append((identity,namespaces))
                by_id[identity] = element
                if root is None:
                    root = element
                else:
                    by_id[parent].append(element)
                    last_child[parent] = element
            elif parent in by_id:
                target = last_child.get(parent)
                if target is None:
                    by_id[parent].text = (by_id[parent].text or '') + (text or '')
                else:
                    target.tail = (target.tail or '') + (text or '')
        # ElementTree includes the selected occurrence's following text in tostring().
        parent, ordinal = self.conn.execute('SELECT parent,ordinal FROM xml_nodes WHERE id=?',(value['node_id'],)).fetchone()
        if parent is not None:
            for node_type,text in self.conn.execute('SELECT type,value FROM xml_nodes WHERE parent=? AND ordinal>? ORDER BY ordinal',(parent,ordinal)):
                if node_type==1:
                    break
                root.tail=(root.tail or '')+(text or '')
                weight+=len(text or '')
                if weight*4>MAX_DEFINITION_BYTES:
                    raise ValueError('Selected XML definition tail exceeds the materialization budget')
        result = {key: item for key, item in value.items() if key not in {'node_id', 'original_file'}}
        result['node'] = root
        result['selectors'] = {id(node): selector for node, selector in walk_nodes(root, result['selector'])}
        return result

    def __iter__(self):
        for (node,) in self.conn.execute('''SELECT d.node FROM canonical_definitions d JOIN selected_definitions s
            ON s.node=d.node ORDER BY d.ordinal'''):
            yield self.hydrate(self.metadata(node))

    def __len__(self):
        return self.conn.execute('SELECT count(*) FROM selected_definitions').fetchone()[0]

    def operations(self):
        for node, channel, context in self.conn.execute('''SELECT d.node,o.channel,o.identity FROM canonical_definitions d JOIN files f ON f.path=d.file
            JOIN notes n ON n.source_relative_path=f.relative_path AND n.source_selector=d.selector AND n.kind='operation'
            JOIN operation_context_index o ON o.definition=n.definition JOIN selected_contexts s ON s.identity=o.identity
            WHERE d.kind='operation' ORDER BY o.ordinal'''):
            value = self.metadata(node)
            value['channel'] = channel
            value['execution_context'] = context
            yield self.hydrate(value)

    def operation_count(self):
        return self.conn.execute('SELECT count(*) FROM selected_contexts').fetchone()[0]

    def resolve_metadata(self, kind, name, owner):
        clause, args = 'kind=? AND name=?', (kind, name)
        path = owner.get('original_file') or str(self.analysis.source_root / owner['path'].relative_to(self.workspace))
        if self.conn.execute('SELECT 1 FROM canonical_definitions WHERE ' + clause + ' AND file=? LIMIT 1', (*args, path)).fetchone():
            clause += ' AND file=?'
            args += (path,)
        elif owner['channel']:
            if self.conn.execute('SELECT 1 FROM canonical_definitions WHERE ' + clause + ' AND channel=? LIMIT 1', (*args, owner['channel'])).fetchone():
                clause += ' AND channel=?'
            else:
                clause += ' AND (channel IS NULL OR channel IN (SELECT target FROM context_imports WHERE channel=?))'
            args += (owner['channel'],)
        count = self.conn.execute('SELECT count(*) FROM canonical_definitions WHERE ' + clause, args).fetchone()[0]
        if count != 1:
            return None, ('Missing' if not count else 'Ambiguous') + ' ' + kind + ' reference: ' + name
        node = self.conn.execute('SELECT node FROM canonical_definitions WHERE ' + clause, args).fetchone()[0]
        return self.metadata(node), None

    def resolve(self, kind, name, owner, scopes):
        context=owner.get('execution_context')
        if context:
            folder={'format':'formats','context':'contexts'}[kind]
            row=self.conn.execute("""SELECT d.node FROM context_bindings b JOIN notes n ON n.path=b.note
                JOIN files f ON f.relative_path=n.source_relative_path JOIN canonical_definitions d
                ON d.file=f.path AND d.selector=n.source_selector WHERE b.context=? AND b.kind='reference' AND b.key=?""",
                (context,folder+':'+name)).fetchone()
            if row is None:
                return None,'Missing or ambiguous '+kind+' reference: '+name
            value=self.metadata(row[0]);value['execution_context']=context
            return self.hydrate(value),None
        value, issue = self.resolve_metadata(kind, name, owner)
        return (self.hydrate(value) if value else None), issue
