"""Documented Composer service semantics supplied only to affected conversion requests."""

import hashlib

_SERVICES = '''A channel's effective dse.ini service-tag registry selects Java implementations.
Loaded service definitions create named configured instances available through that channel's
context. A service type is not an instance identity. Resolve imported/local mappings and actual
runtime names; never assume case-insensitive IDs. Database service poolName references a loaded
connector/pool whose dbType and JDBCDriver identify the target; connection values are deployment
settings. Application initializeFrom(Tag) may delegate to a proprietary JDBC helper. Replace
framework lookup/connector runtime with native providers, not new Composer Service/Context classes.
Read service and step source together for ownership: the supplied regular path disconnects after
work, while the transactional service retains its connection and the step leaves it available.
Do not universally close after each step or share connections process-wide. Preserve evidenced
commit/rollback/auto-commit/timeouts; legacy finalize cleanup is not a native lifecycle mechanism.
Other service types have their own external-client initialization and release contracts, not JDBC
getConnection by assumption. Driver versions come from verified artifact evidence, not tag names.'''


def service_behavior_evidence():
    """Return a compact immutable service contract derived from manual Section 15."""
    return dict(document='embedded:service_behavior_knowledge', heading='Services and Connector Identification',
                content=_SERVICES, content_hash=hashlib.sha256(_SERVICES.encode()).hexdigest())
