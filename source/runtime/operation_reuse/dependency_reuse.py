"""Read approved operation boundaries without requiring a previous run directory."""
import sqlite3

from models.converted_service_contract import ConvertedServiceContract
from tools.converted_service_registry_tools.location import resolve_registry_settings
from tools.shared_artifact_store.location import store_root
from tools.shared_artifact_store.manifests import content_hash, read_manifest


class PublishedDependencies:
    """Look up one application's APIs read-only, recovering candidates from verified snapshots."""
    def __init__(self, profile):
        self.profile = profile
        self.application, path = resolve_registry_settings(profile)
        self.conn, self.cache = None, {}
        if path.is_file():
            conn = None
            try:
                conn = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True)
                if conn.execute("SELECT 1 FROM sqlite_master WHERE name='converted_operation_services'").fetchone():
                    self.conn = conn
            except sqlite3.DatabaseError:
                pass
            finally:
                if conn is not None and conn is not self.conn:
                    conn.close()

    def __enter__(self):
        return self

    def __exit__(self, *error):
        if self.conn is not None:
            self.conn.close()

    def lookup(self, identity):
        """Return a compatible XML service contract; standalone-only delivery is not an API."""
        if identity in self.cache:
            return self.cache[identity]
        channel, operation = identity.split('/', 1)
        contract = None
        if self.conn is not None:
            from tools.converted_service_registry_tools.registry import get_service
            try:
                contract = get_service(self.conn, self.application, channel, operation)
            except (sqlite3.DatabaseError, ValueError, KeyError):
                contract = None
        if contract is None:
            contract = self._snapshot(channel, operation)
        if contract is not None:
            environment = self.profile.deployment_environment
            if 'application/xml' not in contract.media_types or (
                    environment not in contract.addresses and environment not in self.profile.service_environments):
                contract = None
        self.cache[identity] = contract
        return contract

    def _snapshot(self, channel, operation):
        """Use only complete API publications; never promote a standalone artifact into a service."""
        key = content_hash([self.application, channel, operation])
        directory = store_root(self.profile) / 'operations/artifacts' / content_hash(key)
        candidates = []
        for path in directory.glob('*/manifest.json'):
            try:
                manifest = read_manifest(path.parent)
                metadata = manifest['metadata']
                record = metadata.get('service_contract', {})
                if manifest['lookup_key'] != key or metadata.get('api_published') is not True or (
                        record.get('application_id'), record.get('channel'), record.get('operation_id')) != (
                        self.application, channel, operation):
                    continue
                from runtime.operation_reuse.publication import materialize_contract
                value = ConvertedServiceContract.model_validate(materialize_contract(path.parent, manifest))
                candidates.append((metadata.get('published_at', ''), manifest['revision'], value))
            except (OSError, ValueError, KeyError):
                continue
        return max(candidates, key=lambda item: item[:2])[2] if candidates else None
