"""Snapshot the verified Maven project without changing its published build or sources."""
import hashlib
import shutil
from pathlib import Path
from xml.etree import ElementTree as ET

PIT_VERSION = '1.30.1'
JUNIT_PLUGIN_VERSION = '1.2.3'
NAMESPACE = 'http://maven.apache.org/POM/4.0.0'


def snapshot_project(project, folder, bundle):
    """Retain exact build/test inputs, then add PIT only to the isolated copy's POM."""
    project, folder = Path(project), Path(folder)
    folder.mkdir(parents=True)
    shutil.copy2(project / 'pom.xml', folder / 'pom.xml')
    shutil.copytree(project / 'src', folder / 'src')
    originals = {str(p.relative_to(folder)).replace('\\', '/'): hashlib.sha256(p.read_bytes()).hexdigest()
                 for p in sorted(folder.rglob('*')) if p.is_file()}
    classes = _targets(file.path for file in bundle.files if file.path.startswith('src/main/java/'))
    tests = _targets(file.path for file in bundle.files if file.path.startswith('src/test/java/'))
    if not classes or not tests:
        raise ValueError('Mutation measurement requires unit-owned main and test classes')
    tree = ET.parse(folder / 'pom.xml')
    root = tree.getroot()
    namespace = NAMESPACE if root.tag.startswith('{') else ''
    def child(parent, name, text=None):
        node = ET.SubElement(parent, ('{' + namespace + '}' if namespace else '') + name)
        node.text = text
        return node
    def ensure(parent, name):
        existing = parent.find(('{' + namespace + '}' if namespace else '') + name)
        return existing if existing is not None else child(parent, name)
    plugins = ensure(ensure(root, 'build'), 'plugins')
    prefix = '{' + namespace + '}' if namespace else ''
    # A model-provided PIT configuration must not control scope, thresholds or report location.
    for existing in list(plugins):
        if existing.findtext(prefix + 'groupId') == 'org.pitest' and existing.findtext(prefix + 'artifactId') == 'pitest-maven':
            plugins.remove(existing)
    plugin = child(plugins, 'plugin')
    for name, value in [('groupId','org.pitest'), ('artifactId','pitest-maven'), ('version',PIT_VERSION)]: child(plugin,name,value)
    dep = child(child(plugin, 'dependencies'), 'dependency')
    for name, value in [('groupId','org.pitest'), ('artifactId','pitest-junit5-plugin'), ('version',JUNIT_PLUGIN_VERSION)]: child(dep,name,value)
    config = child(plugin, 'configuration')
    for name, value in [('reportsDirectory',str((folder.parent / 'pit-reports').resolve())), ('timestampedReports','false'),
                        ('threads','1'), ('mutationThreshold','0'), ('coverageThreshold','0'), ('testStrengthThreshold','0'),
                        ('failWhenNoMutations','false'), ('timeoutConstant','4000')]: child(config,name,value)
    for name, values in [('targetClasses',classes), ('targetTests',tests), ('outputFormats',['XML','HTML'])]:
        node = child(config,name)
        for value in values: child(node,'param',value)
    # Maven requires an unprefixed project root even when all XML names are namespace-correct.
    if namespace: ET.register_namespace('', namespace)
    tree.write(folder / 'pom.xml', encoding='utf-8', xml_declaration=True)
    return dict(files=originals, target_classes=classes, target_tests=tests,
                measurement_pom_hash=hashlib.sha256((folder / 'pom.xml').read_bytes()).hexdigest())


def _targets(paths):
    """Exact owners plus their nested classes; Foo must not also select FooOther."""
    names = sorted({path.split('/java/',1)[1][:-5].replace('/','.') for path in paths if path.endswith('.java')
                    and not path.endswith(('/package-info.java','/module-info.java'))})
    return [pattern for name in names for pattern in (name, name + '$*')]
