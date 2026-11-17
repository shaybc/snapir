"""Source-driven conversion instructions; initialization belongs to generated native code."""
import json
from pathlib import Path
from format_library.files import digest, inside, read_json, write_json

INSTRUCTION = """Convert only the original classes listed as conversion targets into production native Java.
Implement the supplied com.snapir.format.api.NativeFormat interface without changing the common API.
Generate both format(Object, FormatContext) and unformat(XmlElement, FormatContext).
The source and its inheritance define behavior, not class names or this tool's assumptions.
Translate constructors, initializeFrom(Tag), inherited defaults, settings parsing/validation and all
required business logic. Accept Map<String,String> definition attributes through each exported
component's public constructor. Parse/store those settings inside the generated implementation;
do not return per-attribute mapping metadata. Preserve absent versus explicit values and the
original boolean parsing rules. Runtime fields come from FormatContext.values(), not fixed settings.
Decorators receive NativeFormat wrapped through their constructor. Wrappers receive native child
implementations and their occurrence bindings through their constructor; choose explicit native
arguments and document actual constructor declarations. Reuse approved prerequisites' real APIs.
Never regenerate approved prerequisites or replace their algorithms. Supporting sources are evidence,
not extra exported conversion targets. Flatten framework plumbing into native behavior where needed.
Preserve conditions, delegated calls, beforeFormat/beforeUnformat hooks, null/empty/missing semantics,
namespace URIs/prefixes, attribute behavior, child order, collection semantics, context effects and
exceptions. Do not assume unformat reverses format. Do not prescribe one decorator order: translate
the actual source execution order. A decorator may call its wrapped formatter when the source does.
XmlElement strings are logical unescaped text. Preserve mixed content and escape exactly once in any
wire adapter. Never serialize Java record field names as the business XML schema.
Use ordinary native Java; Jackson XML may be used for genuine wire adapters. No IBM/Composer imports,
runtime objects, reflection-based reconstruction, generic Composer engine or XML tag interpreter.
Original and decompiled sources are behavioral reference only, never runtime dependencies.
Translate inherited behavior into native Java and the supplied common API. Do not preserve IBM
inheritance, delegate to IBM classes or use reflection/class loading to reconstruct Composer.
No original JAR is a target dependency. Ordinary required third-party dependencies must be declared
with pinned coordinates from known_dependencies; if missing, return blocked and explain what is needed.
Do not invent behavior whose required source is unavailable. JARs in the folder are dependencies,
not uploaded source bodies. If their behavior is essential and absent, return blocked with specifics.
No tests, unit tests, compilation scripts, harnesses, original-code execution, or operation conversion.
Return one JSON object and no markdown. Use this shape:
{"status":"generated","files":[{"path":"src/main/java/package/Type.java","content":"complete source"}],
 "components":[{"original_class":"exact target","native_class":"assigned native class",
 "constructors":["actual public Java constructor declaration"],"notes":[]}],
 "dependencies":[],"notes":[]}
Files may contain production .java sources, src/main/resources data, or pom.xml only.
Do not return the shared API files; those are already supplied. Return one components entry for
each target and preserve assigned native names/packages. Helpers may be in the assigned packages.
For incomplete evidence instead return {"status":"blocked","reasons":["precise missing evidence"]}.
Generation is a candidate for human review, not proof of correctness.
"""


def write_prompt(folder, manifest, prerequisites=()):
    """Write an inspectable instruction file and explicit attachment list."""
    lines = [INSTRUCTION, '\nConversion targets and assigned native classes:',
             json.dumps(manifest['native_classes'], indent=2),
             '\nTarget Java version: ' + str(manifest['target_java_version']),
             '\nApproved dependency coordinates: ' + json.dumps(manifest['known_dependencies']),
             '\nOriginal source attachments:']
    lines.extend(item['path'] for item in manifest['files'])
    lines.append('\nRequired members for this standalone conversion (whole original files remain evidence):')
    lines.append(json.dumps(manifest.get('required_members', {}), indent=2))
    lines.append('\nRuntime delegation (preserve child/wrapped calls; do not guess implementations):')
    lines.append(json.dumps(manifest.get('dynamic_calls', {}), indent=2))
    lines.append('\nCommon API attachments:')
    lines.extend(str(path.relative_to(folder)).replace('\\', '/') for path in sorted((folder / 'common-api/src').rglob('*.java')))
    lines.append('\nBinary dependencies (not uploaded as source):')
    lines.extend(item['path'] for item in manifest['binaries'])
    lines.append('\nApproved prerequisite declarations and files:')
    lines.extend(json.dumps(item, indent=2) for item in prerequisites)
    if manifest['dependencies'] and not prerequisites:
        lines.append('Prerequisites not attached yet; convert.cmd refreshes them and refuses conversion until approved.')
    if manifest['blockers']:
        lines.append('\nPreparation blockers:\n' + '\n'.join(manifest['blockers']))
    (folder / 'prompt.txt').write_text('\n'.join(lines), encoding='utf-8')


def build_request(config, folder, manifest):
    """Refresh approved inputs at launch; never send missing or stale prerequisites."""
    from format_library.approval import collect_prerequisites
    from format_library.workspaces import verify_inputs
    verify_inputs(folder, manifest)
    if manifest['blockers']:
        raise ValueError('Preparation is blocked: ' + '; '.join(manifest['blockers']))
    prerequisites = collect_prerequisites(config, folder, manifest)
    write_prompt(folder, manifest, prerequisites)
    attachments = {item['path']: inside(folder, item['path']).read_text(
                       encoding=manifest.get('source_encoding', 'UTF-8')).lstrip('\ufeff')
                   for item in manifest['files']}
    attachments.update({str(path.relative_to(folder)).replace('\\', '/'): path.read_text(encoding='utf-8')
                        for path in sorted((folder / 'common-api/src').rglob('*.java'))})
    for prerequisite in prerequisites:
        for item in prerequisite['files']:
            path = 'prerequisites/' + prerequisite['id'] + '/' + prerequisite['revision'] + '/' + item['path']
            if path.endswith('.java') or path.endswith('pom.xml'):
                attachments[path] = inside(folder, path).read_text(encoding='utf-8')
    request = dict(prompt=(folder / 'prompt.txt').read_text(encoding='utf-8'), attachments=attachments,
        targets=manifest['native_classes'], api_hash=manifest['api_hash'],
        preparation_hash=manifest['preparation_hash'], prerequisites=prerequisites)
    size = len(json.dumps(request, ensure_ascii=False))
    if size > config['request_character_limit']:
        raise ValueError('Request exceeds configured character limit: ' + str(size) + '; nothing was sent or truncated')
    return request
