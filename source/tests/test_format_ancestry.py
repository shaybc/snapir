"""Formats follow source and binary ancestry, independently of method-name heuristics."""
import pytest
from test_behavior_verification_boundaries import boundary_tool
from test_boundary_project_classpath import archive
from models.pipeline_configuration import PipelineConfiguration
from runtime.java_toolchain import java_scope
from runtime.component_conversion.standalone_preparation import prepare_components
from tools.conversion_tools.standalone_sources import component_catalog


def test_ccstring_holder_inherits_common_entries_from_framework_jar(tmp_path, boundary_tool):
    framework = archive(tmp_path / 'framework', {
        'com/ibm/dse/base/Context.java': 'package com.ibm.dse.base; public class Context {}',
        'com/ibm/dse/base/DataElement.java': 'package com.ibm.dse.base; public class DataElement {}',
        'com/ibm/dse/base/DataField.java': 'package com.ibm.dse.base; public class DataField extends DataElement {}',
        'com/ibm/dse/base/FormatElement.java': '''package com.ibm.dse.base; public abstract class FormatElement {
            public abstract String format(Context context);
            public abstract DataElement unformat(String value, Context context);
        }''',
        'com/ibm/dse/base/FieldFormat.java': '''package com.ibm.dse.base; public abstract class FieldFormat extends FormatElement {
            public String format(Context context){return formatField(new DataField());}
            public DataElement unformat(String value,Context context){return unformatField(value,new DataField());}
            public abstract String formatField(DataField field);
            public abstract DataField unformatField(String value,DataField field);
        }''',
        'com/ibm/dse/base/StringFormat.java': '''package com.ibm.dse.base; public class StringFormat extends FieldFormat {
            public String formatField(DataField field){return "";}
            public DataField unformatField(String value,DataField field){return field;}
        }''',
    })
    root = tmp_path / 'workspace'
    folder = root / 'src/main/java/example'; folder.mkdir(parents=True)
    (folder / 'StringFormatHolder.java').write_text('''package example;
        import com.ibm.dse.base.*; public class StringFormatHolder extends StringFormat {
            public String formatField(DataField field){return "holder";}
            public DataField unformatField(String value,DataField field){return field;}
        }''')
    (folder / 'CCString.java').write_text('package example; public class CCString extends StringFormatHolder {}')
    (folder / 'CCXML.java').write_text('''package example; import com.ibm.dse.base.*;
        public class CCXML extends FieldFormat {
            public String formatField(DataField field){return "xml";}
            public DataField unformatField(String value,DataField field){return field;}
        }''')
    selected = PipelineConfiguration(source_root=str(root), conversion_scope='components', component_type='format',
        selected_components=['example.CCString'], channels=[], framework_jars=[str(framework)], java_version=25,
        conversion_strategy='behavior_units', scoped_native_mode='component_first_v1')
    with java_scope(selected):
        found = component_catalog(root, profile=selected)
        assert {'example.CCString', 'example.StringFormatHolder', 'example.CCXML'} <= set(found['format'])
        preparation, _ = prepare_components(selected)
    entries = preparation['boundaries']['boundaries'].values()
    assert len(preparation['standalone_units']) == 2
    for entry in entries:
        assert entry['analysis_status'] == 'identified', entry['issues']
        method = entry['framework_method']
        assert method['implementation_class'] == 'example.CCString'
        assert method['declaring_class'] == 'com.ibm.dse.base.FieldFormat'
        assert 'CCXML' not in method['signature']
        assert method['conversion_target'] is False
    assert {entry['method_name'] for entry in entries} == {'format', 'unformat'}


def test_op_step_catalog_does_not_require_format_ancestry_analysis(tmp_path, monkeypatch):
    from models.java_source_index import JavaSourceIndex
    from xml.etree.ElementTree import fromstring
    path = str(tmp_path / 'Step.java')
    index = JavaSourceIndex(workspace_root=str(tmp_path), classes={'example.Step': [path]})
    documents = {path: fromstring('<source><java_class fqcn="example.Step"><method name="execute"/></java_class></source>')}
    monkeypatch.setattr('tools.conversion_tools.format_candidates.format_candidates',
        lambda *a, **k: (_ for _ in ()).throw(AssertionError('Format analysis must not run')))
    assert component_catalog(tmp_path, catalog=(index, documents), include_formats=False)['op_step'] == ['example.Step']


@pytest.mark.parametrize('returns', ['void', 'com.ibm.dse.base.DataElement', 'com.ibm.dse.base.DataField'])
def test_unformat_preserves_legacy_void_and_accepts_dataelement_subtypes(boundary_tool, returns):
    from test_behavior_verification_boundaries import source, unit, prepared, first
    from tools.behavior_verification.boundaries import build_boundary_report
    body = '' if returns == 'void' else 'return null;'
    sources = [source('context', 'package com.ibm.dse.base; public class Context {}'),
        source('data', 'package com.ibm.dse.base; public class DataElement {}'),
        source('field', 'package com.ibm.dse.base; public class DataField extends DataElement {}'),
        source('format', 'package example; public class Format { public ' + returns +
               ' unformat(String value,com.ibm.dse.base.Context context){' + body + '} }')]
    entry = first(build_boundary_report(prepared(unit('request_unformat', 'example.Format', sources)), tool_jar=boundary_tool))
    assert entry['analysis_status'] == 'identified', entry['issues']
    assert entry['legacy_method']['return_type'] == returns
