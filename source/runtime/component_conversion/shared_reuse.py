"""Reuse neutral candidate code through the existing scoped component validator."""
import json
import logging

from tools.shared_artifact_store.location import store_root
from tools.shared_artifact_store.locking import artifact_lock
from tools.shared_artifact_store.storage import ArtifactStore
from tools.state_store_tools.component_reuse import record_component_use
from runtime.component_conversion.shared_identity import neutral_group, request_identity


def convert_or_reuse(conn, config, profile, plan, group, request, candidate, generate):
    """Reuse only verified neutral code; always rebuild and validate against the current scope."""
    from runtime.behavior_conversion.verification_mode import facts_disabled
    if not getattr(profile, 'cross_run_component_reuse', True) or not neutral_group(plan, group) or facts_disabled(profile):
        generate()
        return False
    key = request_identity(request, profile)
    root = store_root(profile)
    with artifact_lock(root, ['component', key]):
        with ArtifactStore(root, 'components') as store:
            saved = store.find(key)
            rebuilding = saved is None
            saved = saved or store.find_rebuildable(key)
            if saved:
                directory, manifest = saved
                from models.native_component_bundle import NativeComponentBundle
                bundle = NativeComponentBundle.model_validate_json((directory / 'bundle.json').read_text(encoding='utf-8'))
                from runtime.component_conversion.shared_bindings import restore_bundle
                bundle = restore_bundle(bundle, manifest['metadata'].get('bindings'), request)
                try:
                    candidate(bundle, cached=True)
                except (ValueError, OSError) as error:
                    logging.getLogger(__name__).info('Shared component requires current-scope correction: %s', error)
                else:
                    if rebuilding:
                        from runtime.component_conversion.shared_jars import component_package
                        files, metadata = component_package(candidate, bundle, key)
                        directory, manifest = store.publish(key, files, metadata)
                    from tools.shared_artifact_store.maven import install_artifact
                    install_artifact(directory, manifest, profile)
                    record_component_use(conn, config.run_id, config.output_root, key, manifest, group_id=group.group_id,
                                         decision='rebuilt' if rebuilding else 'reused')
                    return True
            bundle = generate()
            from runtime.component_conversion.shared_jars import component_package
            files, metadata = component_package(candidate, bundle, key)
            directory, manifest = store.publish(key, files, metadata)
            from tools.shared_artifact_store.maven import install_artifact
            install_artifact(directory, manifest, profile)
            record_component_use(conn, config.run_id, config.output_root, key, manifest, group_id=group.group_id, decision='converted')
            return False
