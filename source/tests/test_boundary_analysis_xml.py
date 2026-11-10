"""Protect large boundary XML reads and exact source evidence preservation."""

from io import BytesIO
from pathlib import Path
import subprocess
from xml.etree import ElementTree

import pytest

from tools.behavior_verification.analysis_xml import read_analysis_xml
from tools.behavior_verification.java_tool import analyze_entries


class BoundedReport:
    """Reject whole-file reads and exercise parser boundaries with small chunks."""

    def __init__(self, content, chunk_size):
        self.content = content
        self.chunk_size = chunk_size

    def open(self, mode):
        assert mode == 'rb'
        chunk_size = self.chunk_size

        class Stream(BytesIO):
            def read(self, size=-1):
                assert 0 < size <= 64 * 1024
                return super().read(min(size, chunk_size))

        return Stream(self.content)


@pytest.mark.parametrize('chunk_size', [1, 7, 64 * 1024])
def test_bounded_reads_preserve_complete_xml_and_exact_source_text(chunk_size):
    content = ('<?xml version="1.0" encoding="UTF-8"?>'
               '<analysis classpath_protocol="project-classpath-v1"><entry id="unit">'
               '<method source_identity="original"><excerpt>héllo\r\nworld\r! &amp; &lt;x&gt;'
               '&#13;</excerpt></method><issue message="retained"/>'
               '<reachability><code id="code"><excerpt>héllo\r\nworld\r! &amp; &lt;x&gt;'
               '&#13;</excerpt></code></reachability></entry></analysis>').encode('utf-8')
    expected = ElementTree.fromstring(content.replace(b'\r', b'&#13;'))
    actual = read_analysis_xml(BoundedReport(content, chunk_size))
    assert ElementTree.tostring(actual) == ElementTree.tostring(expected)
    assert actual.findtext('entry/method/excerpt') == 'héllo\r\nworld\r! & <x>\r'


def test_large_repeated_excerpts_share_text_without_losing_graph_evidence(tmp_path):
    path = tmp_path / 'output.xml'
    excerpt = 'source evidence\r\n' * 8192
    with path.open('wb') as stream:
        stream.write(b'<analysis><entry id="unit"><reachability>')
        for index in range(64):
            stream.write(f'<code id="code-{index}"><excerpt>'.encode())
            stream.write(excerpt.encode())
            stream.write(b'</excerpt></code>')
        stream.write(b'</reachability></entry></analysis>')
    report = read_analysis_xml(path)
    nodes = report.findall('entry/reachability/code')
    assert [node.get('id') for node in nodes] == [f'code-{index}' for index in range(64)]
    text = nodes[0].findtext('excerpt')
    assert text == excerpt
    assert all(node.findtext('excerpt') is text for node in nodes)


def test_truncated_report_is_rejected():
    with pytest.raises(ElementTree.ParseError):
        read_analysis_xml(BoundedReport(b'<analysis><entry id="unit">', 7))


@pytest.mark.parametrize('collect_checklists', [True, False])
def test_analyzer_handoff_avoids_whole_file_reads(tmp_path, monkeypatch, collect_checklists):
    tool = tmp_path / 'analyzer.jar'
    tool.write_bytes(b'pinned analyzer')

    def run(command, progress_path, runner, *, output_path):
        manifest = ElementTree.parse(Path(command[-2])).getroot()
        entry = manifest.find('scope/entry')
        assert entry.get('checklist') == (None if collect_checklists else 'false')
        output_path.write_bytes(b'<analysis><entry id="unit"><method><excerpt>a\r\nb</excerpt>'
                                b'</method></entry></analysis>')
        return subprocess.CompletedProcess(command, 0, '', '')

    def forbid_whole_file_read(path):
        pytest.fail('Boundary output must not be loaded with Path.read_bytes')

    from types import SimpleNamespace
    boundary = SimpleNamespace(unit_id='unit', implementation_class='example.Work', method_name='execute',
        return_contract='void', kind='configured_step', parameter_contract=[], setup_class_roots=[], setup_bindings=[])
    monkeypatch.setattr('tools.behavior_verification.java_tool.run_with_progress', run)
    monkeypatch.setattr(Path, 'read_bytes', forbid_whole_file_read)
    report, fingerprint = analyze_entries({'scope': dict(sources=[], boundaries=[boundary])}, tool,
                                          collect_checklists=collect_checklists)
    assert report.findtext('entry/method/excerpt') == 'a\r\nb'
    assert len(fingerprint) == 64
