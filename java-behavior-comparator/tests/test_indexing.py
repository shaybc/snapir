"""Indexing preserves source spans, inheritance and read-only binary evidence."""
from pathlib import Path
from comparator.input_catalog import catalog
from comparator.source_index import index
from comparator.evidence import Evidence
from support import sources, settings


def test_inherited_helpers_and_exact_same_line_member_spans(tmp_path):
    request=sources(tmp_path,original='package old; public class Old extends Base {}')
    old=Path(request['original']['sources'][0])
    (old/'Base.java').write_text('package old; public class Base { public String format(String v){return helper(v);} private String helper(String v){return v;} public void unrelated(){} }')
    work=tmp_path/'reports';work.mkdir()
    data=index(catalog(request,work,settings()),settings(),work)
    evidence=Evidence(data);scope=evidence.scope('original','old.Old',['format'])
    members=[evidence.chunks[identity] for identity in scope['ids']]
    assert any(member['name']=='helper' for member in members)
    assert not any(member['name']=='unrelated' for member in members)
    method=next(member for member in members if member['name']=='format')
    assert 'unrelated' not in method['source'] and 'private String helper' not in method['source']
    assert method['facts'] and method['file'].endswith('Base.java')


def test_unrelated_unreadable_source_does_not_hide_valid_target(tmp_path):
    request=sources(tmp_path)
    (Path(request['original']['sources'][0])/'Bad.java').write_bytes(bytes([0xff]))
    work=tmp_path/'reports';work.mkdir()
    data=index(catalog(request,work,settings()),settings(),work)
    assert 'original::old.Old' in data['classes']
    assert any('Bad.java' in warning for warning in data['warnings'])


def test_wildcard_java_import_does_not_shadow_actual_source_ancestor(tmp_path):
    request=sources(tmp_path,original='package old; import java.util.*; import base.*; public class Old extends Base {}')
    dep=tmp_path/'dependencies';dep.mkdir()
    (dep/'Base.java').write_text('package base; public class Base { public String format(String v){return v;} }')
    request['original']['dependency_sources']=[str(dep)]
    work=tmp_path/'reports';work.mkdir()
    data=index(catalog(request,work,settings()),settings(),work)
    scope=Evidence(data).scope('original','old.Old',['format'])
    assert not scope['gaps']
    assert any(data['chunks'][identity]['owner']=='base.Base' for identity in scope['ids'])
