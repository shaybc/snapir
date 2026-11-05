"""Create or incrementally grow an owned local fixture without deleting user directories."""

import hashlib
import json
import math
from pathlib import Path
import shutil

from tools.huge_bank_demo.java_copies import channel_steps, copy_step_sources
from tools.huge_bank_demo.operation_copies import operation_documents, copy_operations

MANIFEST = 'huge-bank-demo.json'
VERSION = 1


def _write_file(path, content):
    """Write new generated content, accepting identical files after an interrupted family."""
    if path.exists():
        if path.read_bytes() != content:
            raise ValueError(f'Refusing to overwrite different existing content: {path}')
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)


def _save_report(output, report):
    """Atomically record the last complete family, so growth can resume safely."""
    temporary = output / (MANIFEST + '.tmp')
    temporary.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    temporary.replace(output / MANIFEST)


def generate_demo(source, output, files=1000):
    """Copy the Bank Demo and append complete replicas until the minimum file count is met.

    Existing generated folders can grow when their seed fingerprint matches. Nothing is
    deleted; arbitrary existing folders and conflicting new-family files are rejected.
    No model, network, mapper, database or package-manager access is required.
    """
    source, output = Path(source).resolve(), Path(output).resolve()
    if files < 1:
        raise ValueError('--files must be positive')
    if source == output or source.is_relative_to(output) or output.is_relative_to(source):
        raise ValueError('Source and output directories must not contain each other')
    if not (source / 'composer/Workspace').is_dir():
        raise ValueError(f'Bank Demo workspace is missing: {source}')
    seed_files = sorted(path for path in source.rglob('*') if path.is_file())
    fingerprint = hashlib.sha256()
    for path in seed_files:
        fingerprint.update(path.relative_to(source).as_posix().encode() + b'\0')
        fingerprint.update(hashlib.sha256(path.read_bytes()).digest())
    documents, steps = operation_documents(source), channel_steps(source)
    if not documents or not steps:
        raise ValueError('The seed must contain operation XML and channel-specific Java steps')
    operations = sum(1 for _, root in documents for _ in root.iter('CCDSEServerOperation'))
    occurrences = sum(1 for _, root in documents for _ in root.iter('opStep'))
    family_files = len(documents) + len(steps)
    base_count = len(seed_files) + 1  # Include the generated manifest.
    replicas = max(1, math.ceil(max(0, files - base_count) / family_files))
    manifest_path = output / MANIFEST
    if output.exists() and any(output.iterdir()):
        if not manifest_path.is_file():
            raise ValueError(f'Output is not an owned Huge Bank Demo: {output}')
        report = json.loads(manifest_path.read_text(encoding='utf-8'))
        if report.get('generator_version') != VERSION or report.get('source_fingerprint') != fingerprint.hexdigest():
            raise ValueError('Seed or generator changed; choose a new output folder')
        for path in seed_files:
            copied = output / path.relative_to(source)
            if not copied.is_file() or copied.read_bytes() != path.read_bytes():
                raise ValueError(f'Copied seed file was changed or removed: {copied}')
    else:
        print(f'Copying original Bank Demo ({len(seed_files)} files) to {output}', flush=True)
        shutil.copytree(source, output, dirs_exist_ok=True)
        report = dict(generator_version=VERSION, source_fingerprint=fingerprint.hexdigest(), replicas=0)
        _save_report(output, report)
    completed = report['replicas']
    base_java = sum(path.suffix == '.java' for path in seed_files)
    last_report = base_count + completed * family_files
    for replica in range(completed + 1, replicas + 1):
        suffix = f'Huge{replica:05d}'
        for relative, content in copy_step_sources(steps, suffix):
            _write_file(output / relative, content)
        for relative, content in copy_operations(documents, steps, suffix, replica):
            _write_file(output / relative, content)
        report.update(replicas=replica, files=base_count + replica * family_files,
                      operations=operations * (replica + 1), op_step_occurrences=occurrences * (replica + 1),
                      java_files=base_java + replica * len(steps))
        _save_report(output, report)
        if report['files'] - last_report >= 250 or replica == replicas:
            print(f"Generated {report['files']} files; {report['operations']} operations; family {replica}/{replicas}.", flush=True)
            last_report = report['files']
    return report
