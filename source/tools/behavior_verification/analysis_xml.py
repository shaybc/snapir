"""Read large boundary analysis reports without whole-file buffers or repeated excerpts."""

from xml.etree import ElementTree


class _AnalysisTreeBuilder(ElementTree.TreeBuilder):
    """Share identical source excerpts while retaining every XML element and attribute."""

    def __init__(self):
        super().__init__()
        self.excerpts = {}

    def end(self, tag):
        element = super().end(tag)
        if tag == 'excerpt' and element.text is not None:
            element.text = self.excerpts.setdefault(element.text, element.text)
        return element


def read_analysis_xml(path):
    """Return the complete report tree from bounded binary reads, preserving literal CRs.

    Repeated source excerpts share immutable text; no analysis evidence is discarded.
    File errors and XML parse errors propagate to the existing caller.
    """
    parser = ElementTree.XMLParser(target=_AnalysisTreeBuilder())
    with path.open('rb') as stream:
        while chunk := stream.read(64 * 1024):
            # Match the source-preserving treatment used by the input manifest.
            parser.feed(chunk.replace(b'\r', b'&#13;'))
    return parser.close()
