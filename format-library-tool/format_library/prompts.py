"""Source-driven conversion instructions; initialization belongs to generated native code."""
import json
from pathlib import Path
from format_library.files import digest, inside, read_json, write_json

INSTRUCTION = """Convert only the original classes listed as conversion targets into production native Java.
Implement the supplied com.snapir.format.api.NativeFormat interface without changing the common API.
Generate both format(Object, FormatContext) and unformat(XmlElement, FormatContext).
The source and its inheritance define behavior, not class names or this tool's assumptions.
required_members identifies the source members needed by this conversion. Original files remain
complete evidence; unrelated helper methods in them are not conversion duties or dependencies.
If required_members marks a dynamic call, preserve its runtime delegation rather than inventing
a concrete implementation. Do not omit conditions or initialization inside the required scope.
Translate constructors, initializeFrom(Tag), inherited defaults, settings parsing/validation and all
required business logic. Accept Map<String,String> definition attributes through each exported
component's public constructor. Parse/store those settings inside the generated implementation;
do not return per-attribute mapping metadata. Preserve absent versus explicit values and the
original boolean parsing rules. Runtime fields come from FormatContext.values(), not fixed settings.
Decorators receive NativeFormat wrapped through their constructor. Wrappers receive native child
implementations and their occurrence bindings through their constructor; choose explicit native
arguments and document actual constructor declarations. Reuse approved prerequisites' real APIs.
Never regenerate approved prerequisites or replace their algorithms. Supporting sources are evidence,
not extra exported conversion targets. Use the approved native base classes and their protected
hooks/constructors for shared behavior. Implement only the remaining differences in this component.
Inherit from an approved base when that is its documented extension contract; otherwise delegate
through the supplied native API. Do not flatten, copy, recreate, or bypass approved foundation logic.
Preserve conditions, delegated calls, beforeFormat/beforeUnformat hooks, null/empty/missing semantics,
namespace URIs/prefixes, attribute behavior, child order, collection semantics, context effects and
exceptions. Do not assume unformat reverses format. Do not prescribe one decorator order: translate
the actual source execution order. A decorator may call its wrapped formatter when the source does.
XmlElement strings are logical unescaped text. Preserve mixed content and escape exactly once in any
wire adapter. Never serialize Java record field names as the business XML schema.
Use ordinary native Java; Jackson XML may be used for genuine wire adapters. No IBM/Composer imports,
runtime objects, reflection-based reconstruction, generic Composer engine or XML tag interpreter.
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

FOUNDATION_INSTRUCTION = """Convert this selected shared foundation group into production native Java.
Use the supplied NativeFormat, XmlElement and FormatContext API unchanged wherever applicable.
Shared format/decorator bases may be abstract. Supporting utility types/interfaces do not have to
implement NativeFormat or expose both directions. Several original ancestors may collapse into one
native class; behavior may also be split across cooperating native types. Preserve all selected
original behavior, including inherited initialization/defaults, hooks, delegation, context effects,
exceptions, and overridable extension points. Preserve protected hooks required by later subclasses.
Translate initializeFrom/attribute handling into native constructors/settings code. Constructors
that accept definition settings use Map<String,String> attributes; abstract helpers/interfaces need
not have such a constructor. No per-attribute settings mapping metadata is requested.
Define clear constructor, public method and protected hook contracts for downstream conversions.
Explain how a subclass overrides only its differences, and which behavior the native foundation owns.
Approved prerequisites are frozen: use their actual APIs and never regenerate their algorithms.
This task explicitly permits a reusable native foundation, not an IBM runtime under different names.
Do not recreate Composer loaders, reflective class factories, Tag engines, operation routing or a
generic XML-definition interpreter. Use only native data types and the common API. No com.ibm
imports/executable references or original JAR target dependencies. Supporting original code is
evidence only; exported coverage may claim only the selected original classes.
Preserve source-defined format/unformat differences; do not assume the methods are inverses.
Do not invent behavior absent from source. A JAR supplies types, not method-body evidence.
If required behavior is unavailable, return status blocked with precise reasons.
Only use pinned third-party dependencies from known_dependencies. No tests, unit tests, compilation
scripts, original-code execution, harnesses or operation conversion.
Return one JSON object, without prose or markdown:
{"status":"generated","files":[{"path":"src/main/java/package/Base.java","content":"complete source"}],
 "components":[{"native_class":"fully.qualified.NativeBase","kind":"abstract_class",
 "covered_original_classes":["exact original class"],"constructors":["actual constructor"],
 "methods":["actual public method declaration"],"hooks":["actual protected extension declaration"],
 "integration_notes":"How to construct, subclass or delegate; preserved behavior and extension duties"}],
 "dependencies":[],"notes":[]}
Allowed export kinds: class, abstract_class, interface. Constructors/methods/hooks are lists of actual
Java declarations and may be empty where appropriate. Every selected original class must be covered
by at least one export; multiple exports may jointly implement the same original behavior.
Use the assigned native package, but suggested per-original native names are not mandatory for a
combined foundation. Return complete files for every export and any required native companions.
Do not return common API source files. Files are production .java, src/main/resources data, or pom.xml.
Instead of guessing, return {"status":"blocked","reasons":["precise missing evidence"]}.
Generated output is a candidate for human review, not compiled or behaviorally verified code.
"""


def write_prompt(folder, manifest, prerequisites=()):
    """Write an inspectable instruction file and explicit attachment list."""
    from format_library.prompt_evidence import source_attachments
    attachments, omitted, mixed = source_attachments(folder, manifest, prerequisites)
    foundation = manifest.get('stage') == 'foundation'
    lines = [FOUNDATION_INSTRUCTION if foundation else INSTRUCTION,
             '\nFoundation targets and suggested native names:' if foundation else '\nConversion targets and assigned native classes:',
             json.dumps(manifest['native_classes'], indent=2),
             '\nTarget Java version: ' + str(manifest['target_java_version']),
             '\nApproved dependency coordinates: ' + json.dumps(manifest['known_dependencies']),
             '\nOriginal source attachments:']
    lines.extend(attachments)
    lines.append('\nRequired source members (other helper methods are retained evidence, not conversion duties):')
    lines.append(json.dumps(manifest.get('required_members', {}), indent=2))
    lines.append('\nOriginal sources omitted because approved native exports own their behavior:')
    lines.append(json.dumps(omitted, indent=2))
    lines.append('\nMixed files retained as evidence; approved portions must not be regenerated:')
    lines.append(json.dumps(mixed, indent=2))
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
    from format_library.foundation_planning import verify_selection
    verify_inputs(folder, manifest)
    verify_selection(config, manifest)
    if manifest['blockers']:
        raise ValueError('Preparation is blocked: ' + '; '.join(manifest['blockers']))
    prerequisites = collect_prerequisites(config, folder, manifest)
    write_prompt(folder, manifest, prerequisites)
    from format_library.prompt_evidence import source_attachments
    attachments, omitted, mixed = source_attachments(folder, manifest, prerequisites)
    attachments.update({str(path.relative_to(folder)).replace('\\', '/'): path.read_text(encoding='utf-8')
                        for path in sorted((folder / 'common-api/src').rglob('*.java'))})
    for prerequisite in prerequisites:
        for item in prerequisite['files']:
            path = 'prerequisites/' + prerequisite['id'] + '/' + prerequisite['revision'] + '/' + item['path']
            if path.endswith('.java') or path.endswith('pom.xml'):
                attachments[path] = inside(folder, path).read_text(encoding='utf-8')
    request = dict(prompt=(folder / 'prompt.txt').read_text(encoding='utf-8'), attachments=attachments,
        targets=manifest['native_classes'], stage=manifest['stage'], policy=manifest['policy'],
        omitted_original_sources=omitted, mixed_original_sources=mixed, api_hash=manifest['api_hash'],
        preparation_hash=manifest['preparation_hash'], prerequisites=prerequisites)
    size = len(json.dumps(request, ensure_ascii=False))
    if size > config['request_character_limit']:
        raise ValueError('Request exceeds configured character limit: ' + str(size) + '; nothing was sent or truncated')
    return request
