"""Select the common JDK and Maven options for this standalone validator only."""
import os
from pathlib import Path
import re
import shutil
import subprocess


def select_java(settings):
    """Require the common Java major version and return its executable and environment."""
    environment = os.environ.copy()
    home = settings.get('java_home') or environment.get('JAVA_HOME')
    if home:
        environment['JAVA_HOME'] = home
        environment['PATH'] = str(Path(home) / 'bin') + os.pathsep + environment.get('PATH', '')
    java = shutil.which('java', path=environment.get('PATH'))
    if not java:
        raise ValueError('Java not found; set java_home in the common converter YAML')
    version = subprocess.run([java, '-version'], env=environment, capture_output=True, text=True, timeout=10)
    major = re.search(r'version\s+"(\d+)', version.stdout + version.stderr)
    if version.returncode or not major or int(major[1]) != settings['java_version']:
        raise ValueError('Selected JDK does not match common java_version=' + str(settings['java_version']))
    return java, environment


def maven_options(settings):
    """Use common Maven connection settings, never original Composer jars as native dependencies."""
    arguments = []
    if settings.get('maven_settings_path'):
        arguments += ['-s', settings['maven_settings_path']]
    if settings.get('maven_local_repository'):
        arguments += ['-Dmaven.repo.local=' + settings['maven_local_repository']]
    return arguments
