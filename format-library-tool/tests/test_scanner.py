"""Exercise the real metadata-only scanner on synthetic inheritance and decorator code."""
import json
import os
import subprocess
from pathlib import Path
import sys
import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from format_library.configuration import load_config
from format_library.discovery import scan, SCANNER_JAR
from format_library.planning import build_plan


def test_source_inheritance_and_decorator_precedence(tmp_path):
    if not SCANNER_JAR.is_file():
        pytest.skip('Build the scanner to run its integration regression')
    root = tmp_path / 'workspace'
    files = {
        'com/ibm/dse/base/FormatElement.java': 'package com.ibm.dse.base; public abstract class FormatElement {}',
        'com/ibm/dse/base/FormatDecorator.java': 'package com.ibm.dse.base; public abstract class FormatDecorator extends FormatElement {}',
        'example/Holder.java': 'package example; public abstract class Holder extends com.ibm.dse.base.FormatElement {}',
        'example/CCString.java': 'package example; public class CCString extends Holder { private Mode mode = Mode.TEXT; }',
        'example/Mode.java': 'package example; public enum Mode { TEXT }',
        'example/NilDecorator.java': 'package example; public class NilDecorator extends com.ibm.dse.base.FormatDecorator {}',
        'example/Fake.java': 'package example; public class Fake {public String format(){return "";}}',
    }
    for name, value in files.items():
        path = root / 'src/main/java' / name
        path.parent.mkdir(parents=True, exist_ok=True); path.write_text(value)
    path = tmp_path / 'config.yaml'
    path.write_text(yaml.safe_dump(dict(source_root=str(root), output_root=str(tmp_path / 'work'),
        java_home=os.environ.get('JAVA_HOME'), java_version=25)))
    result = scan(load_config(path))
    assert result['classes']['example.CCString']['kind'] == 'format'
    assert result['classes']['example.NilDecorator']['kind'] == 'decorator'
    assert result['classes']['example.Fake']['kind'] == 'support'
    assert 'example.Mode' in result['classes']['example.CCString']['dependencies']
    assert result['classes']['example.Mode']['kind'] == 'support'
    plan = build_plan(result)
    assert {member for group in plan['groups'] for member in group['members']} == {'example.CCString', 'example.NilDecorator'}
    assert not any(group['blockers'] for group in plan['groups']), plan


def test_binary_ancestry_and_copied_framework_dependencies(tmp_path):
    if not SCANNER_JAR.is_file():
        pytest.skip('Build the scanner first')
    from format_library.configuration import java_environment
    from format_library.workspaces import prepare
    import shutil
    config_path = tmp_path / 'config.yaml'
    root = tmp_path / 'workspace'
    folder = root / 'src/main/java/example'; folder.mkdir(parents=True)
    (folder / 'CCString.java').write_text('package example; public class CCString extends com.ibm.dse.base.StringFormat {}')
    framework = tmp_path / 'framework'
    base = framework / 'src/com/ibm/dse/base'; base.mkdir(parents=True)
    (base / 'FormatElement.java').write_text('package com.ibm.dse.base; public abstract class FormatElement {}')
    (base / 'StringFormat.java').write_text('''package com.ibm.dse.base;
        public class StringFormat extends FormatElement {
            static { if (true) throw new IllegalStateException("scanner must never execute this"); }
        }''')
    classes = framework / 'classes'; classes.mkdir()
    config_path.write_text(yaml.safe_dump(dict(source_root=str(root), output_root=str(tmp_path / 'work'),
        java_home=os.environ.get('JAVA_HOME'), java_version=25)))
    config = load_config(config_path)
    _, environment = java_environment(config)
    javac = shutil.which('javac', path=environment['PATH'])
    jar = shutil.which('jar', path=environment['PATH'])
    subprocess.run([javac, '--release', '17', '-d', str(classes), *map(str, base.glob('*.java'))], env=environment, check=True, capture_output=True)
    archive = framework / 'framework.jar'
    subprocess.run([jar, '--create', '--file', str(archive), '-C', str(classes), '.'], env=environment, check=True, capture_output=True)
    config['framework_jars'] = [str(archive)]
    result = scan(config)
    assert result['classes']['example.CCString']['kind'] == 'format'
    plan = build_plan(result)
    assert not plan['groups'][0]['blockers'], plan
    workspace = prepare(config, plan)[0]
    assert len(list((workspace / 'jars').rglob('*.jar'))) == 1


def test_referenced_source_uses_own_project_jars(tmp_path):
    if not SCANNER_JAR.is_file():
        pytest.skip('Build the scanner first')
    from format_library.configuration import java_environment
    import shutil
    workspace = tmp_path / 'workspace'
    a, b = workspace / 'A', workspace / 'B'
    for project in (a, b):
        (project / 'src').mkdir(parents=True)
    (a / 'src/a').mkdir()
    (b / 'src/b').mkdir()
    (a / 'src/a/Child.java').write_text('package a; public class Child extends b.Holder {}')
    (a / 'src/a/Plain.java').write_text('package a; public class Plain extends vendor.Base {}')
    (b / 'src/b/Holder.java').write_text('package b; public class Holder extends vendor.Base {}')
    path = tmp_path / 'config.yaml'
    path.write_text(yaml.safe_dump(dict(source_root=str(workspace), output_root=str(tmp_path / 'work'),
        java_home=os.environ.get('JAVA_HOME'), java_version=25)))
    config = load_config(path)
    _, environment = java_environment(config)
    javac, jar = (shutil.which(name, path=environment['PATH']) for name in ('javac', 'jar'))
    libraries = []
    for name, ancestor in [('good', ' extends com.ibm.dse.base.FormatElement'), ('bad', '')]:
        root = tmp_path / name
        (root / 'src/vendor').mkdir(parents=True)
        base = root / 'src/vendor/Base.java'
        base.write_text('package vendor; public class Base' + ancestor + ' {}')
        files = [base]
        if ancestor:
            api = root / 'src/com/ibm/dse/base/FormatElement.java'
            api.parent.mkdir(parents=True)
            api.write_text('package com.ibm.dse.base; public abstract class FormatElement {}')
            files.append(api)
        (root / 'classes').mkdir()
        subprocess.run([javac, '--release', '17', '-d', str(root / 'classes'), *map(str, files)],
                       env=environment, check=True, capture_output=True)
        library = root / (name + '.jar')
        subprocess.run([jar, '--create', '--file', str(library), '-C', str(root / 'classes'), '.'],
                       env=environment, check=True, capture_output=True)
        libraries.append(library.as_posix())
    (a / '.classpath').write_text('<classpath><classpathentry kind="src" path="src"/>'
        '<classpathentry kind="src" path="/B"/><classpathentry kind="lib" path="' + libraries[1] + '"/></classpath>')
    (b / '.classpath').write_text('<classpath><classpathentry kind="src" path="src"/>'
        '<classpathentry kind="lib" path="' + libraries[0] + '"/></classpath>')
    result = scan(config)
    assert result['classes']['a.Child']['kind'] == 'format'
    assert result['classes']['a.Plain']['kind'] == 'support'
    assert result['classes']['b.Holder']['kind'] == 'format'
