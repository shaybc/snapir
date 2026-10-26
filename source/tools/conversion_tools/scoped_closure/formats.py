"""Resolve selected format graphs and effective occurrence trees from verified XML."""

from collections import deque

from models.conversion_models import ClosureStatus
from models.scoped_format_node import ScopedFormatNode
from tools.conversion_tools.scoped_closure.collection_policy import INDEXED_WRAPPERS, effective_children
from tools.conversion_tools.scoped_closure.source_evidence import child_selectors, SourceEvidenceError


def reference_name(element):
    """Read Composer reference attributes without changing the referenced ID's spelling."""
    return element.get('refid') or element.get('refId') or ''


class FormatResolver:
    """Follow only role, inline, switch, and transitive references selected in this context."""

    def __init__(self, access, context, sources, mappings, issue):
        self.access, self.context, self.sources = access, context, sources
        self.mappings, self.issue = mappings, issue
        self.nodes, self.roles, self.java_classes = {}, {}, set()
        self.pending, self.visited = deque(), set()

    def bind(self, name):
        """Resolve a name through the imported context; missing bindings never search inventory."""
        try:
            reference = self.access.resource(self.context, 'formats:' + name)
            if reference.kind != 'format':
                raise ValueError('Selected format binding has the wrong entity kind')
            self.pending.append(reference)
            return reference.definition_id
        except ValueError as exc:
            self.issue(name, str(exc), ClosureStatus.BLOCKED_MISSING_FORMAT)
            return None

    def resolve(self, operation, switches):
        """Collect operation format roles, inline definitions, and per-occurrence switches."""
        roles = {child.get('name', ''): child for child in operation if child.tag == 'refFormat'}
        for role, child in roles.items():
            name = reference_name(child)
            if not role or not name:
                self.issue(self.context.operation_id, 'Operation format reference requires name and refid',
                           ClosureStatus.BLOCKED_MISSING_FORMAT)
            identity = self.bind(name) if name else None
            if identity:
                self.roles[role] = identity
        # The registry of root fmtDef siblings is keyed independently of opStep labels.
        inline = {child.get('id'): child for child in operation if child.tag == 'fmtDef' and child.get('id')}
        for name in inline:
            self.bind(name)
        resolved_switches = {}
        for step_note, values in switches.items():
            resolved_switches[step_note] = {}
            for condition, name in values.items():
                identity = self.bind(name)
                if identity:
                    resolved_switches[step_note][condition] = identity
        if any(switches.values()) and 'csErrorReplyFormat' not in self.roles:
            self.issue(self.context.operation_id, 'Return-body switching requires csErrorReplyFormat',
                       ClosureStatus.BLOCKED_MISSING_FORMAT)
        while self.pending:
            reference = self.pending.popleft()
            if reference.definition_id in self.visited:
                continue
            self.visited.add(reference.definition_id)
            try:
                element = self.sources.xml(reference)
                if element.tag != 'fmtDef':
                    raise SourceEvidenceError('Format binding does not select fmtDef')
                self.nodes[reference.definition_id] = self._node(
                    element, reference.evidence['source_selector'], reference, reference.definition_id)
            except (ValueError, OSError) as exc:
                self.issue(reference.definition_id, str(exc), ClosureStatus.BLOCKED_MISSING_FORMAT)
        return resolved_switches

    def _decorator(self, element):
        return 'decorator' in self.mappings.get(element.tag, '').lower()

    def _mapped_class(self, element):
        if element.tag in ('fmtDef', 'refFmt', 'refFormat'):
            return None
        fqcn = self.mappings.get(element.tag)
        if fqcn:
            self.java_classes.add(fqcn)
        else:
            self.issue(element.tag, 'Formatter/decorator tag has no consuming-channel mapping',
                       ClosureStatus.BLOCKED_UNKNOWN_TAG)
        return fqcn

    def _node(self, element, selector, root, owner):
        if element.tag == 'fmtDef' and selector != root.evidence['source_selector']:
            owner = self.access.nested_definition(self.context, root, selector).definition_id
        node = ScopedFormatNode(occurrence_id=owner + ':' + selector, definition_id=owner,
            source_selector=selector, tag=element.tag, attributes=dict(element.attrib),
            collection_kind='definition' if element.tag == 'fmtDef' else (
                'indexed' if element.tag in INDEXED_WRAPPERS else 'keyed'),
            java_class=self._mapped_class(element))
        if element.tag in ('refFmt', 'refFormat'):
            name = reference_name(element)
            if not name:
                self.issue(node.occurrence_id, 'Format reference has no refid', ClosureStatus.BLOCKED_MISSING_FORMAT)
            else:
                node.reference_definition_id = self.bind(name)
        selectors = {id(child): path for child, path in child_selectors(element, selector)}
        previous = None
        children = list(element) if element.tag == 'fmtDef' else effective_children(element, self._decorator)
        if element.tag == 'fmtDef' and sum(not self._decorator(child) for child in children) != 1:
            self.issue(selector, 'fmtDef must identify one format body; multiple/empty bodies need explicit evidence')
        for child in children:
            path = selectors[id(child)]
            if self._decorator(child) and previous is not None:
                previous.decorators.append(dict(occurrence_id=owner + ':' + path, source_selector=path,
                    tag=child.tag, attributes=dict(child.attrib), java_class=self._mapped_class(child)))
            else:
                if self._decorator(child):
                    self.issue(path, 'Decorator has no preceding formatter in its parent scope')
                previous = self._node(child, path, root, owner)
                node.children.append(previous)
        return node
