"""Create a source-complete Maven reactor without modifying native operation Java."""
import hashlib
import json
import shutil
from pathlib import Path
from xml.etree import ElementTree
from runtime.service_generation.deployment_configuration import service_name


MODULES = ('integration-runtime', 'test-support', 'application')


def prepare_reactor(root, profile):
    """Include both private source projects and a root build using the existing pinned versions."""
    root = Path(root)
    source = Path(__file__).resolve().parents[2]
    root.mkdir(parents=True, exist_ok=True)
    for name, original in [('integration-runtime', source / 'integration-runtime-java'),
                           ('test-support', source / 'behavior-verification-java')]:
        target = root / name
        target.mkdir(exist_ok=True)
        shutil.copyfile(original / 'pom.xml', target / 'pom.xml')
        shutil.copytree(original / 'src', target / 'src', dirs_exist_ok=True)
        from tools.maven_dependency_tools.shared_policy_pom import apply_shared_policy
        apply_shared_policy(target / 'pom.xml', profile)
    (root / 'application').mkdir(exist_ok=True)
    pom = ElementTree.Element('project', xmlns='http://maven.apache.org/POM/4.0.0')
    for name, value in [('modelVersion', '4.0.0'), ('groupId', 'il.co.dcd.generated'),
                        ('artifactId', service_name(root.parent.parent.name,root.parent.name) + '-microservice'), ('version', '1.0.0'), ('packaging', 'pom')]:
        ElementTree.SubElement(pom, name).text = value
    modules = ElementTree.SubElement(pom, 'modules')
    for name in MODULES:
        ElementTree.SubElement(modules, 'module').text = name
    (root / 'pom.xml').write_bytes(ElementTree.tostring(pom, encoding='utf-8', xml_declaration=True))
    (root / '.gitignore').write_text('**/target/\n*.log\n', encoding='utf-8')
    (root / 'README.md').write_text(
        '# Production microservice\n\nBuild all sources and run their tests with `mvn clean verify` from this folder.\n'
        'The private integration runtime and test helper are included as Maven source modules.\n'
        'Third-party dependencies require configured Maven repository access.\n'
        'Build the application image from this folder after Maven packaging.\n'
        'Helm chart values are under `helm/`. Configure JDBC, image/namespace settings and Secret references before deployment.\n', encoding='utf-8')
    return root / 'application'


def reactor_hash(root):
    """Bind reuse to every module POM/source without including build output or audit records."""
    root = Path(root)
    files = [root / 'pom.xml']
    for name in MODULES:
        files.extend([root / name / 'pom.xml', *sorted((root / name / 'src').rglob('*'))])
    return hashlib.sha256(json.dumps([(str(p.relative_to(root)), hashlib.sha256(p.read_bytes()).hexdigest())
        for p in files if p.is_file()], sort_keys=True).encode()).hexdigest()


def verify_reactor(root, context):
    """Run normal Maven verify across all modules, including all application and library tests."""
    root = Path(root)
    result = context.verifier._run(context.verifier._arguments() + ['verify'], root)
    counts = {key: 0 for key in ('tests', 'failures', 'errors', 'skipped')}
    for module in MODULES:
        for path in (root / module / 'target/surefire-reports').glob('TEST-*.xml'):
            suite = ElementTree.parse(path).getroot()
            for key in counts:
                counts[key] += int(suite.get(key, '0'))
    passed = result.returncode == 0 and counts['tests'] > 0 and not any(counts[k] for k in ('failures', 'errors', 'skipped'))
    return dict(passed=passed, counts=counts, stdout=result.stdout, stderr=result.stderr)
