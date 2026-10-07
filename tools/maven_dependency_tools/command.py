"""Locate the installed Maven launcher, including mvn.cmd on Windows."""

import shutil


def maven_executable() -> str:
    """Return Maven's PATH-resolved executable; retain missing-command errors."""
    return shutil.which("mvn") or "mvn"
