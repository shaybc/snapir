"""Production member scope excludes unused helpers without hiding reached missing dependencies."""
import os
from pathlib import Path
import sys
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from format_library.configuration import load_config
from format_library.discovery import scan, SCANNER_JAR
from format_library.planning import build_plan
from format_library.classpaths import inventory


def test_qualified_jdk_names_virtual_hooks_and_per_formatter_helper_scope(tmp_path):
    if not SCANNER_JAR.is_file():
        pytest.skip('Build scanner first')
    root = tmp_path / 'workspace'
    files = {
        'com/ibm/dse/base/FormatElement.java': 'package com.ibm.dse.base; public abstract class FormatElement { public abstract String format(); }',
        'example/Field.java': 'package example; public abstract class Field extends com.ibm.dse.base.FormatElement { public String format(){return value();} protected abstract String value(); }',
        'example/Good.java': '''package example; public class Good extends Field {
            protected String value(){return Common.clean("value")+java.util.Calendar.getInstance().getTimeInMillis();}
            private missing.UnusedFormatterType unrelated(){return null;}
        }''',
        'example/Bad.java': 'package example; public class Bad extends Field { protected String value(){return Common.database();} }',
        'example/Common.java': '''package example; public class Common {
            static final String PREFIX = "prefix";
            public static <T> String clean(T value){return PREFIX+value;}
            public static String database(){missing.Database.connect();return "";}
            public static missing.UnusedSoapType soap(){return null;}
        }''',
    }
    for name, content in files.items():
        path = root / 'src/main/java' / name
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(content)
    config_path = tmp_path / 'config.yaml'
    (root / '.classpath').write_text('''<classpath>
        <classpathentry kind="src" path="src/main/java"/>
        <classpathentry kind="con" path="unavailable.production.container"/>
        <classpathentry kind="con" path="org.eclipse.jdt.junit.JUNIT_CONTAINER/4"/>
        <classpathentry kind="lib" path="missing-declared.jar"/>
    </classpath>''')
    config_path.write_text(yaml.safe_dump(dict(source_root=str(root), output_root=str(tmp_path / 'work'),
        java_home=os.environ.get('JAVA_HOME'), java_version=25,
        foundation_groups={'base': ['com.ibm.dse.base.FormatElement', 'example.Field']})))
    result = scan(load_config(config_path))
    good = result['dependency_scopes']['example.Good']
    bad = result['dependency_scopes']['example.Bad']
    assert not any(item['issues'] for item in good.values()), good
    assert any(item['issues'] for item in bad.values()), bad
    assert any('clean' in member for member in good['example.Common']['required_members'])
    assert not any('database' in member or 'soap' in member for member in good['example.Common']['required_members'])
    assert 'java.util.Calendar' in good['example.Good']['dependencies']
    assert not any('UnusedSoapType' in symbol or 'UnusedFormatterType' in symbol for symbol in result['unresolved_dependencies'])
    plan = build_plan(result)
    good_group = next(group for group in plan['groups'] if group['members'] == ['example.Good'])
    bad_group = next(group for group in plan['groups'] if group['members'] == ['example.Bad'])
    assert not good_group['blockers'], good_group
    assert bad_group['blockers'], bad_group
    assert good_group['required_members']['example.Common']
    from format_library.workspaces import prepare
    import json
    prepared = prepare(load_config(config_path), plan, ['example.Good'])
    manifest = json.loads((prepared[-1] / 'component.json').read_text())
    assert not manifest['blockers'], manifest
    assert any('missing-declared.jar' in warning for warning in manifest['dependency_warnings'])


def test_explicit_super_constructor_does_not_pull_unused_constructor_dependencies(tmp_path):
    if not SCANNER_JAR.is_file():
        pytest.skip('Build scanner first')
    root = tmp_path / 'workspace'
    files = {
        'com/ibm/dse/base/FormatElement.java': 'package com.ibm.dse.base; public abstract class FormatElement {}',
        'example/Format.java': '''package example; public class Format extends com.ibm.dse.base.FormatElement {
            public String format(){return new Helper("x").value();}
        }''',
        'example/Base.java': '''package example; public class Base {
            public Base(){missing.UnusedDatabase.connect();}
            public Base(String value){}
        }''',
        'example/Helper.java': '''package example; public class Helper extends Base {
            private String prefix = prefix();
            public Helper(String value){super(value);}
            private String prefix(){return "prefix";}
            public String value(){return prefix;}
        }''',
    }
    for name, text in files.items():
        path = root / 'src/main/java' / name
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(text)
    config = tmp_path / 'config.yaml'
    config.write_text(yaml.safe_dump(dict(source_root=str(root), output_root=str(tmp_path / 'work'),
        java_home=os.environ.get('JAVA_HOME'), java_version=25)))
    result = scan(load_config(config))
    scope = result['dependency_scopes']['example.Format']
    assert not any(item['issues'] for item in scope.values()), scope
    assert any('prefix' in value for value in scope['example.Helper']['required_members'])
    assert any('String' in value for value in scope['example.Base']['required_members'])
    assert not any('UnusedDatabase' in value for value in result['unresolved_dependencies'])


def test_test_classpath_entries_and_sources_do_not_block_production(tmp_path):
    root = tmp_path / 'workspace'
    (root / 'src/main/java').mkdir(parents=True)
    (root / 'src/test/java').mkdir(parents=True)
    (root / 'extra-tests').mkdir()
    (root / 'src/main/java/Main.java').write_text('class Main {}')
    (root / 'src/test/java/BrokenTest.java').write_text('not valid Java')
    (root / 'extra-tests/OtherTest.java').write_text('not valid Java')
    (root / '.classpath').write_text('''<classpath>
      <classpathentry kind="src" path="src/main/java"/>
      <classpathentry kind="src" path="extra-tests"><attributes><attribute name="test" value="true"/></attributes></classpathentry>
      <classpathentry kind="con" path="org.eclipse.jdt.junit.JUNIT_CONTAINER/4"/>
      <classpathentry kind="lib" path="missing-test.jar"><attributes><attribute name="test" value="true"/></attributes></classpathentry>
      <classpathentry kind="con" path="production-container"/>
    </classpath>''')
    path = tmp_path / 'config.yaml'
    path.write_text(yaml.safe_dump(dict(source_root=str(root), output_root=str(tmp_path / 'work'))))
    result = inventory(load_config(path))
    assert [Path(item['file']).name for item in result['sources']] == ['Main.java']
    assert result['projects'][0]['libraries'] == []
    assert result['projects'][0]['issues'] == ['Unresolved Eclipse container: production-container']


@pytest.mark.parametrize('scope,blocked', [('test', False), ('compile', True), ('provided', True)])
def test_maven_test_only_dependencies_are_not_production_blockers(tmp_path, scope, blocked):
    root = tmp_path / 'workspace'; root.mkdir()
    (root / 'Main.java').write_text('class Main {}')
    (root / 'pom.xml').write_text('<project><dependencies><dependency><scope>' + scope +
        '</scope></dependency></dependencies></project>')
    path = tmp_path / 'config.yaml'
    path.write_text(yaml.safe_dump(dict(source_root=str(root), output_root=str(tmp_path / 'work'))))
    assert bool(inventory(load_config(path))['projects'][0]['issues']) is blocked
