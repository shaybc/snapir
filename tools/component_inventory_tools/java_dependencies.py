"""Propagate original operation consumers through statically resolved Java sources."""

from pathlib import Path

from models.java_source_dependencies import JavaSourceDependencyGraph, JavaSourceDependency, JavaDependencyIssue, JavaDependencyUse
from tools.component_inventory_tools.identity import stable_id
from tools.java_analysis_tools.source_dependencies.parser import parse_source_references
from tools.java_analysis_tools.source_dependencies.resolution import resolve_reference
from tools.component_inventory_tools.dependency_order import dependency_first_order


def build_java_dependency_graph(workspace, source_index, implementations, configured_uses):
    """Resolve source-reference sites, then traverse each XML use without counting paths twice."""
    workspace = Path(workspace).resolve()
    by_path = {str((workspace / implementation.source_path).resolve()): implementation for implementation in implementations}
    analysis = parse_source_references(by_path)
    graph = JavaSourceDependencyGraph()
    edges = {}
    for document in analysis.findall("source"):
        path = str(Path(document.get("path")).resolve())
        caller = by_path.get(path)
        if caller is None:
            continue
        for reference in document.findall("reference"):
            targets, issue = resolve_reference(reference, document, source_index, path)
            if issue:
                graph.issues.append(JavaDependencyIssue(implementation_id=caller.implementation_id, message=issue))
            for target_path in targets:
                target = by_path.get(str(Path(target_path).resolve()))
                if target is None or target.implementation_id == caller.implementation_id:
                    continue
                offset = int(reference.get("offset"))
                identity = stable_id(caller.implementation_id, target.implementation_id, offset)
                edges[identity] = JavaSourceDependency(dependency_id=identity,
                    caller_implementation_id=caller.implementation_id, target_implementation_id=target.implementation_id,
                    source_offset=offset, reference_kind=reference.get("kind"), reference_name=reference.get("name"))
    for issue in analysis.findall("issue"):
        owner = by_path.get(str(Path(issue.get("path")).resolve())) if issue.get("path") else None
        if owner:
            graph.issues.append(JavaDependencyIssue(implementation_id=owner.implementation_id, message="Java syntax: " + issue.get("message")))
        else:
            raise ValueError("JDK parser reported an unscoped source error: " + issue.get("message"))
    graph.dependencies = [edges[key] for key in sorted(edges)]
    outgoing = {}
    for edge in graph.dependencies:
        outgoing.setdefault(edge.caller_implementation_id, []).append(edge)
    indirect = {}
    for use in configured_uses:
        if not use.implementation_id or use.resolution_issue:
            continue
        visited = set()
        pending = [use.implementation_id]
        while pending:
            caller = pending.pop()
            if caller in visited:
                continue
            visited.add(caller)
            for edge in outgoing.get(caller, []):
                pending.append(edge.target_implementation_id)
        dependencies = {caller: {edge.target_implementation_id for edge in outgoing.get(caller, [])} for caller in visited}
        try:
            callers_first = list(reversed(dependency_first_order(visited, dependencies)))
            counts = {use.implementation_id: 1}
        except ValueError:
            # Consumers are still reported, but cycles cannot imply finite use counts.
            callers_first = sorted(visited)
            counts = {caller: 1 for caller in visited}
        for caller in callers_first:
            count = counts.get(caller, 0)
            for edge in outgoing.get(caller, []):
                identity = stable_id(use.use_id, edge.dependency_id)
                indirect[identity] = JavaDependencyUse(use_id=identity, source_use_id=use.use_id,
                    dependency_id=edge.dependency_id, operation_key=use.operation_key, operation_id=use.operation_id,
                    channel=use.channel, implementation_id=edge.target_implementation_id, reference_count=max(count, 1))
                counts[edge.target_implementation_id] = counts.get(edge.target_implementation_id, 0) + count
    graph.uses = [indirect[key] for key in sorted(indirect)]
    graph.issues = list({(issue.implementation_id, issue.message): issue for issue in graph.issues}.values())
    return graph
