"""Verify large fixture growth, connected copies, preserved Java behavior and safe output ownership."""

import hashlib
import re
import shutil
import subprocess
from pathlib import Path
from xml.etree import ElementTree

import pytest

from tools.huge_bank_demo.generation import generate_demo

SEED = Path(__file__).resolve().parents[2] / 'bank-demo'


def test_default_size_connections_and_shared_implementations(tmp_path):
    before = {path: hashlib.sha256(path.read_bytes()).hexdigest() for path in SEED.rglob('*') if path.is_file()}
    output = tmp_path / 'huge-bank-demo'
    report = generate_demo(SEED, output)
    assert report['files'] == len([path for path in output.rglob('*') if path.is_file()])
    assert report['files'] >= 1000
    operations, step_count, implementations = {}, 0, set()
    for path in (output / 'composer/Workspace').rglob('*.xml'):
        root = ElementTree.parse(path).getroot()
        for operation in root.iter('CCDSEServerOperation'):
            channel = path.parts[path.parts.index('Channel') + 1]
            key = (channel, operation.get('id'))
            assert key not in operations
            operations[key] = operation
            steps = list(operation.iter('opStep'))
            step_count += len(steps)
            ids = {step.get('id') for step in steps}
            for step in steps:
                implementations.add(step.get('implClass'))
                for attribute, value in step.attrib.items():
                    if attribute.startswith('on') and attribute.endswith('Do'):
                        assert value in ids | {'next', 'end'}, (path, attribute, value)
    assert len(operations) == report['operations']
    assert step_count == report['op_step_occurrences']
    for (channel, _), operation in operations.items():
        for step in operation.iter('opStep'):
            target = step.get('opExecuteName')
            effective_channel = step.get('onlyFor', channel).upper()
            if target:
                assert (effective_channel, target) in operations
                assert ('Huge' in target) == ('Huge' in operation.get('id'))
    classes = set()
    for path in (output / 'composer/Workspace').rglob('*.java'):
        package = re.search(r'^package\s+([\w.]+);', path.read_text(), re.MULTILINE)[1]
        classes.add(package + '.' + path.stem)
    assert implementations <= classes
    assert any('Huge' in name for name in implementations)
    assert any('.operations.' in name and 'Huge' not in name for name in implementations)
    assert all(hashlib.sha256(path.read_bytes()).hexdigest() == digest for path, digest in before.items())


def test_growth_is_repeatable_and_preserves_existing_families(tmp_path):
    output = tmp_path / 'generated'
    first = generate_demo(SEED, output, 100)
    existing = {path: path.read_bytes() for path in output.rglob('*') if path.is_file() and path.suffix != '.json'}
    assert generate_demo(SEED, output, 100) == first
    grown = generate_demo(SEED, output, 200)
    assert grown['files'] >= 200 and grown['replicas'] > first['replicas']
    assert all(path.read_bytes() == content for path, content in existing.items())
    assert generate_demo(SEED, output, 50) == grown


def test_rejects_unowned_output_and_changed_seed(tmp_path):
    output = tmp_path / 'unowned'
    output.mkdir()
    (output / 'keep.txt').write_text('user data')
    with pytest.raises(ValueError, match='not an owned'):
        generate_demo(SEED, output, 100)
    assert (output / 'keep.txt').read_text() == 'user data'
    with pytest.raises(ValueError, match='must not contain'):
        generate_demo(SEED, SEED / 'nested', 100)
    with pytest.raises(ValueError, match='must be positive'):
        generate_demo(SEED, tmp_path / 'invalid', 0)
    seed = tmp_path / 'seed'
    shutil.copytree(SEED, seed)
    generated = tmp_path / 'generated'
    generate_demo(seed, generated, 100)
    (seed / 'README.md').write_text('changed seed')
    with pytest.raises(ValueError, match='Seed or generator changed'):
        generate_demo(seed, generated, 200)


def test_copied_java_compiles_and_keeps_fraud_step_behavior(tmp_path):
    if not shutil.which('javac') or not shutil.which('java'):
        pytest.skip('A JDK is required')
    output = tmp_path / 'generated'
    generate_demo(SEED, output, 100)
    harness = tmp_path / 'CopiedStepCheck.java'
    harness.write_text('''import com.ibm.dse.base.*;
import com.ibm.il.dse.cc.service.communication.http.HTTPService;
import com.ibm.il.dse.operations.internet.service.*;
public class CopiedStepCheck {
    public static void main(String[] args) throws Exception {
        for (CCOperationStep step : new CCOperationStep[] {new CallFraudDetection(), new CallFraudDetectionHuge00001()}) {
            Context context = new Context();
            context.setValueAt("Amount", new java.math.BigDecimal("12.50"));
            step.setContext(context);
            step.setService("FraudDetectionService", new HTTPService());
            if (step.execute() != 0 || !"ALLOW".equals(context.getValueAt("FraudDecision"))
                    || !Integer.valueOf(7).equals(context.getValueAt("FraudScore"))) throw new AssertionError();
        }
    }
}''')
    classes = tmp_path / 'classes'
    classes.mkdir()
    arguments = tmp_path / 'sources.args'
    arguments.write_text('\n'.join('"' + path.as_posix() + '"' for path in [*output.rglob('*.java'), harness]))
    compiled = subprocess.run(['javac', '-encoding', 'UTF-8', '-d', str(classes), '@' + str(arguments)], capture_output=True, text=True, timeout=120)
    assert compiled.returncode == 0, compiled.stderr
    executed = subprocess.run(['java', '-cp', str(classes), 'CopiedStepCheck'], capture_output=True, text=True, timeout=30)
    assert executed.returncode == 0, executed.stderr
