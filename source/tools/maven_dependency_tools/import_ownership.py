"""Disambiguate approved dependency candidates by actual classes in their resolved JARs."""
from functools import lru_cache
from pathlib import Path
import re
import tempfile
from zipfile import ZipFile
from tools.maven_dependency_tools.repository_verifier import MavenRepositoryVerifier
from tools.conversion_tools.scoped_reuse.fingerprints import revision


@lru_cache(maxsize=16)
def repository_path(settings_path,settings_hash,local_repository):
    """Respect Maven's effective repository, including user settings, without recording secrets."""
    if local_repository:return Path(local_repository)
    verifier=MavenRepositoryVerifier(settings_path,[],local_repository)
    with tempfile.TemporaryDirectory(prefix='snapir-import-owner-') as folder:
        result=verifier._run(verifier._arguments()+['--quiet','help:evaluate','-Dexpression=settings.localRepository','-DforceStdout'],folder)
    if result.returncode:raise ValueError('Maven could not locate its effective repository for import ownership')
    return Path(re.sub(r'\x1b\[[0-9;]*m','',result.stdout).strip())


def verified_import_owner(profile,imp,candidates):
    """Return a unique real JAR owner; absent or multiple owners remain unresolved."""
    settings=getattr(profile,'maven_settings_path',None)
    repository=repository_path(settings,revision(settings) if settings else None,getattr(profile,'maven_local_repository',None))
    name=imp['name'];wildcard=imp['wildcard']=='true';static=imp['static']=='true'
    if static and not wildcard:name=name.rsplit('.',1)[0]
    target=name.replace('.','/')+('/' if wildcard and not static else '.class')
    owners=[]
    for item in candidates:
        path=repository.joinpath(*item.group_id.split('.'),item.artifact_id,item.version,item.artifact_id+'-'+item.version+'.jar')
        if not path.is_file():continue
        with ZipFile(path) as archive:
            names=archive.namelist()
            found=any(value.startswith(target) and value.endswith('.class') for value in names) if wildcard and not static else target in names
        if found:owners.append(item)
    return owners[0] if len(owners)==1 else None
