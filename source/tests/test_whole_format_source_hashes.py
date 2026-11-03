"""Whole-format cached evidence retains original line endings without relaxing freshness."""
import hashlib
from copy import deepcopy
import pytest
from tools.java_analysis_tools.java_source_reader import read_java_source
from tools.conversion_tools.scoped_workflow.units import restore_cached_source_text
from runtime.behavior_conversion.metadata_checklist_evidence import source_catalog
from test_behavior_verification_boundaries import boundary_tool,unit,source,prepared,first


@pytest.mark.parametrize('newline,bom',[('\r\n',False),('\r',False),('\n',False),('\r\n',True)])
def test_exact_and_cached_format_sources_match_original_hash(tmp_path,newline,bom):
    text=('\ufeff' if bom else '')+'class Format {'+newline+'}'+newline
    raw=text.encode('utf-8');path=tmp_path/'Format.java';path.write_bytes(raw)
    digest=hashlib.sha256(raw).hexdigest()
    normalized=text.replace('\r\n','\n').replace('\r','\n')
    assert read_java_source(str(path),expected_hash=digest)==normalized
    assert read_java_source(str(path),expected_hash=digest,preserve_line_endings=True)==text
    operation=dict(behavior_request=dict(java_origins=[dict(status='verified_source',definition_id='source',
        source_file=str(path),source_hash=digest)]),units=[dict(sources=[dict(identity='source',content_hash=digest,content=normalized)])])
    original=deepcopy(operation)
    restore_cached_source_text(operation)
    source=operation['units'][0]['sources'][0]
    assert source['content']==text and source['content_hash']==digest
    assert len(source_catalog(dict(sources=[source]),{},{}))==1
    restore_cached_source_text(operation)
    altered=deepcopy(original);altered['units'][0]['sources'][0]['content']+='// changed'
    with pytest.raises(ValueError,match='Cached source content differs'):
        restore_cached_source_text(altered)
    altered=deepcopy(original);altered['units'][0]['sources'][0]['content_hash']='wrong'
    with pytest.raises(ValueError,match='Cached source revision differs'):
        restore_cached_source_text(altered)
    path.write_bytes(raw+b'// changed')
    with pytest.raises(ValueError,match='revision differs from intake'):
        restore_cached_source_text(original)


@pytest.mark.parametrize('newline',['\n','\r\n','\r'])
def test_real_parser_round_trip_preserves_source_excerpts(boundary_tool,newline):
    from runtime.java_toolchain import java_scope
    from models.pipeline_configuration import PipelineConfiguration
    from tools.behavior_verification.boundaries import build_boundary_report
    text=newline.join(['package example;','public class Work {',' public int execute() {',
        '  int value = 7;','  return value;',' }','}'])
    original=unit(sources=[source('work',text)])
    with java_scope(PipelineConfiguration(java_version=25)):
        report=first(build_boundary_report(prepared(original),tool_jar=boundary_tool))
    assert report['analysis_status']=='identified',report['issues']
    assert report['legacy_method']['excerpt'] in text
    assert report['parser_checklist']['status']=='extracted'
