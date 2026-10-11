"""Resolve Git for portable verification utilities without changing import paths.

PF8_GIT, when present, is an explicit executable path or a command name on PATH.
Paths may contain spaces; they are passed as one argument, never through a shell.
An explicit relative path is relative to the caller's current working directory.
When PF8_GIT is absent, only the caller's PATH is searched for ``git``. A missing
or empty PATH does not implicitly search the current directory or system defaults.
Invalid overrides fail without falling back to another executable. The returned
path is absolute so subsequent subprocess calls may safely change directory.

Utilities running with Python -I load this file using runpy.run_path, anchored
to their own __file__ and the repository's tools directory.
"""

import os
from pathlib import Path
import shutil
import subprocess


def resolve_git():
    """Return an absolute executable Git path, or raise an actionable error."""
    explicit = 'PF8_GIT' in os.environ
    requested = os.environ['PF8_GIT'] if explicit else 'git'
    origin = 'PF8_GIT' if explicit else 'PATH'
    if not requested:
        raise RuntimeError('PF8_GIT is empty; set an executable Git path or unset it to use PATH.')
    search_path = os.environ.get('PATH', '')
    if not os.path.dirname(requested) and not search_path:
        raise RuntimeError(f'Cannot resolve Git from {origin}: PATH is missing or empty. Set PF8_GIT to an executable Git path.')
    candidate = shutil.which(requested, path=search_path)
    if candidate is None:
        raise RuntimeError(f'Cannot resolve executable Git from {origin}: {requested!r}. Set PF8_GIT to an executable Git path or install Git on PATH.')
    executable = Path(candidate).resolve()
    if not executable.is_file() or not os.access(executable, os.X_OK):
        raise RuntimeError(f'Git resolved from {origin} is not an executable file: {executable}')
    try:
        version = subprocess.run(
            [str(executable), '--version'], capture_output=True, text=True,
            timeout=10, check=False,
        )
    except (OSError, subprocess.TimeoutExpired, UnicodeError) as exc:
        raise RuntimeError(f'Cannot execute Git resolved from {origin}: {executable}: {exc}') from exc
    if version.returncode != 0 or not version.stdout.startswith('git version '):
        raise RuntimeError(f'Executable resolved from {origin} did not report a Git version: {executable} (exit {version.returncode}).')
    return str(executable)
