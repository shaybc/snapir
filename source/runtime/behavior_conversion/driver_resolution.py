"""Verify source-selected driver dependencies and target-Java class loading."""

import os
import subprocess
import tempfile
from pathlib import Path
from models.maven_dependency import MavenDependency

_PROBE = '''public class DriverProbe {
 public static void main(String[] args) throws Exception {
  Class<?> type = Class.forName(args[0], false, Thread.currentThread().getContextClassLoader());
  if (!java.sql.Driver.class.isAssignableFrom(type)) throw new IllegalArgumentException("Not a JDBC driver");
 }
}'''


def verify_driver_load(driver_class, libraries, profile):
    """Load the driver without initialization or database access on the configured JDK.

    This checks platform linkage only; it does not claim vendor/server compatibility.
    """
    from runtime.java_toolchain import java_environment
    environment = java_environment(profile.java_version, profile.java_home)
    executable = Path(environment['JAVA_HOME']) / 'bin' / ('java.exe' if os.name == 'nt' else 'java')
    with tempfile.TemporaryDirectory(prefix='snapir-driver-probe-') as directory:
        source = Path(directory) / 'DriverProbe.java'
        source.write_text(_PROBE, encoding='utf-8')
        result = subprocess.run([str(executable), '--class-path', os.pathsep.join(libraries), str(source), driver_class],
            env=environment, capture_output=True, text=True, timeout=60, check=False)
    if result.returncode:
        raise ValueError('Driver cannot load on configured Java ' + str(profile.java_version) + ': ' + driver_class +
                         '. Select a verified compatible driver version. ' + result.stderr[-1200:])


def verify_connections(records, profile, verifier, classpath):
    """Verify exact artifact owners before putting their versions into prompts."""
    for record in records:
        if record.resource_kind != 'jdbc' or not record.driver_class:
            continue
        from constants import SERVICE_DRIVER_DEPENDENCY_CANDIDATES
        candidates = ([record.driver_dependency] if record.driver_dependency else []) + [item['dependency'] for item in
            SERVICE_DRIVER_DEPENDENCY_CANDIDATES if item['driver_class'] == record.driver_class and
            profile.java_version in item['java_versions']]
        failures = []
        for proposal in candidates:
            try:
                dependency = MavenDependency.model_validate(proposal)
                from tools.maven_dependency_tools.policy import validate_dependency_policy
                validate_dependency_policy(dependency, profile.allowed_ibm_artifacts)
                if dependency.scope not in {'compile', 'runtime'} or record.driver_class not in dependency.required_classes:
                    raise ValueError('Driver proposal must name ' + record.driver_class + ' in required_classes and use a production scope')
                verifier(dependency)
                libraries = verifier.resolved_runtime_classpath(dependency) if hasattr(verifier, 'resolved_runtime_classpath') else classpath.libraries
                verify_driver_load(record.driver_class, libraries, profile)
                record.driver_dependency = dependency.model_dump(mode='json')
                record.issues = [issue for issue in record.issues if not issue.startswith('Driver coordinates/version')]
                record.ownership['driver_verification'] = dict(java_version=profile.java_version,
                    artifact_verified=True, platform_load_verified=True, server_compatibility='not_tested',
                    selection='workspace version' if proposal == candidates[0] and record.driver_candidates else 'approved compatible proposal')
                break
            except (OSError, ValueError, subprocess.SubprocessError) as exc:
                failures.append(str(exc))
        else:
            record.issues.extend(failures)

