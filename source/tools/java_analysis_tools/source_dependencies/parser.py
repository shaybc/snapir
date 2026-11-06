"""Invoke the installed JDK parser once per source inventory, with temporary reports."""

import subprocess
from runtime.java_toolchain import run_java, java_version, java_scan_inactivity_timeout
import tempfile
import logging
from pathlib import Path
from xml.etree import ElementTree
from tools.java_analysis_tools.source_dependencies.analysis_runtime import analyzer_command


def _parse_batch(paths, *, strip_bom=False):
    """Yield one source or diagnostic at a time from a bounded compiler task."""
    paths = sorted(set(map(str, paths)))
    if not paths:
        return
    with tempfile.TemporaryDirectory(prefix="snapir-java-references-") as temporary:
        root = Path(temporary)
        manifest = ElementTree.Element("sources")
        for path in paths:
            ElementTree.SubElement(manifest, "source", path=path)
        ElementTree.ElementTree(manifest).write(root / "sources.xml", encoding="utf-8", xml_declaration=True)
        inactivity = java_scan_inactivity_timeout()
        try:
            result = run_java([*analyzer_command(), str(root / "sources.xml"), str(root / "references.xml"), *(['--strip-bom'] if strip_bom else [])],
                                    capture_output=True, text=True, inactivity_timeout_seconds=inactivity,
                                    activity_path=root / "references.xml", check=False)
        except subprocess.TimeoutExpired as exc:
            raise ValueError(f"Java source dependency scanner stopped after {inactivity} seconds without output or result-file activity; "
                             "configure java_scan_inactivity_timeout_seconds to allow longer inactive periods") from exc
        except OSError as exc:
            raise ValueError(f"Could not launch or access the JDK source dependency scanner: {exc}") from exc
        if result.returncode:
            raise ValueError("JDK source dependency parser failed: " + result.stderr[-2000:])
        for event, element in ElementTree.iterparse(root / "references.xml", events=('end',)):
            if element.tag in {'source', 'issue'}:
                yield element
                element.clear()


def iter_source_references(paths, *, strip_bom=False, cache=None, batch_files=250, batch_bytes=8 * 1024 * 1024):
    """Parse bounded batches, reusing byte-identical syntax while resolving globally elsewhere."""
    from tools.composer_mapper_tools.mapped_scope import current_mapped, source_syntax
    mapped = current_mapped()
    if mapped is not None:
        yield from source_syntax(mapped, paths)
        return
    from tools.state_store_tools.workspace_analysis import content_hash
    logger = logging.getLogger(__name__)
    paths = sorted(set(str(Path(path).resolve()) for path in paths))
    batch, weight, hashes = [], 0, {}

    def flush():
        if not batch:
            return
        logger.info('Java syntax batch: %s files, %s source bytes; cache hits=%s.', len(batch), weight, cache.hits if cache else 0)
        documents, issues = {}, []
        for document in _parse_batch(batch, strip_bom=strip_bom):
            # Diagnostics follow source nodes, so retain only this batch until it is complete.
            copy = ElementTree.fromstring(ElementTree.tostring(document))
            if copy.tag == 'source':
                documents[str(Path(copy.get('path')).resolve())] = copy
            else:
                issues.append(copy)
        related_issues = {}
        for path, document in documents.items():
            related = [issue for issue in issues if issue.get('path') and str(Path(issue.get('path')).resolve()) == path]
            related_issues[path] = related
            for issue in related:
                document.append(issue)
        if cache:
            cache.store_batch(documents, hashes, strip_bom)
        for path, document in documents.items():
            yield document
            yield from related_issues[path]
        yield from (issue for issue in issues if not issue.get('path'))

    for path in paths:
        digest = content_hash(path) if cache else None
        cached = cache.read(path, digest, strip_bom) if cache else None
        if cached is not None:
            yield cached
            yield from cached.findall('issue')
            continue
        size = Path(path).stat().st_size
        if batch and (len(batch) >= batch_files or weight + size > batch_bytes):
            yield from flush()
            batch, weight, hashes = [], 0, {}
        batch.append(path)
        hashes[path] = digest
        weight += size
    yield from flush()


def parse_source_references(paths, *, strip_bom=False):
    """Keep the standalone tree API; inventory consumes the streaming iterator instead."""
    root = ElementTree.Element('analysis')
    for document in iter_source_references(paths, strip_bom=strip_bom):
        root.append(document)
    return root
