"""Validate explicit Mapper generation settings before touching an output vault."""

from pathlib import Path


def mapper_command(settings, *, markdown=False, filter_channel=True, validate_output=True):
    """Build one validated invocation for standalone intake and pipeline startup."""
    if validate_output:
        errors, generate = validate_mapper_output(settings)
        if errors:
            raise ValueError('; '.join(errors))
        if not generate:
            raise ValueError('Mapper generation requires an existing COMPOSER_MAPPER_JAR')
    command = ['java', '-jar', settings['COMPOSER_MAPPER_JAR'], '--root', settings['COMPOSER_ROOT'],
               '--vault', settings['VAULT_ROOT']]
    if settings.get('COMPOSER_MAPPER_VAULT_LAYOUT', 'legacy') == 'scoped':
        command.extend(['--vault-layout', 'scoped', '--workspace-id', settings['SOURCE_WORKSPACE_ID'], '--md', 'true'])
    elif markdown:
        command.append('--md')
    channels = settings.get('TARGET_CHANNELS') or []
    if filter_channel and settings.get('RUN_MODE') == 'single_channel' and len(channels) == 1:
        command.extend(['--channel', channels[0]])
    return command


def validate_mapper_output(settings):
    """Return configuration errors and whether a Mapper JAR will be invoked.

    Existing vaults are inputs when no JAR is configured. Generation requires an
    empty destination outside the source tree; scoped identity must be explicit.
    """
    jar = settings.get('COMPOSER_MAPPER_JAR')
    generate = bool(jar and Path(jar).is_file())
    if not generate:
        return [], False
    errors = []
    layout = settings.get('COMPOSER_MAPPER_VAULT_LAYOUT', 'legacy')
    if layout not in ('legacy', 'scoped'):
        errors.append('COMPOSER_MAPPER_VAULT_LAYOUT must be legacy or scoped')
    if layout == 'scoped' and not str(settings.get('SOURCE_WORKSPACE_ID') or '').strip():
        errors.append('Scoped Mapper generation requires a stable SOURCE_WORKSPACE_ID')
    root, vault = Path(settings['COMPOSER_ROOT']).resolve(), Path(settings['VAULT_ROOT']).resolve()
    if vault.is_relative_to(root) or root.is_relative_to(vault):
        errors.append('Mapper vault must be separate from the source tree')
    if vault.exists() and (not vault.is_dir() or any(vault.iterdir())):
        errors.append('Mapper generation requires a new or empty vault directory')
    return errors, True
