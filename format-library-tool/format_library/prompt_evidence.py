"""Choose AI evidence at approved ownership boundaries; keep original archives intact."""
from format_library.files import inside


def source_attachments(folder, manifest, prerequisites):
    """Omit only files completely covered by approved exports, never mixed target/support files."""
    covered = {name for item in prerequisites for name in item['members']}
    selected, omitted, mixed = [], [], []
    for item in manifest['files']:
        names = set(manifest.get('file_classes', {}).get(item['original'], []))
        if not names:
            names = {name for name, source in manifest['original_classes'].items()
                     if source.get('file') == item['original']}
        overlap = names & covered
        if names and names <= covered and not names.intersection(manifest['members']):
            omitted.append(dict(path=item['path'], sha256=item['sha256'], covered_classes=sorted(names)))
            continue
        selected.append(item)
        if overlap:
            mixed.append(dict(path=item['path'], covered_classes=sorted(overlap),
                instruction='Covered declarations are evidence only; do not regenerate approved behavior'))
    attachments = {item['path']: inside(folder, item['path']).read_text(encoding='utf-8-sig') for item in selected}
    return attachments, omitted, mixed
