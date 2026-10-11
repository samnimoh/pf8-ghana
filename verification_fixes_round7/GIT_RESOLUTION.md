# Git discovery in verification utilities

The nine corrected review utilities load `tools/git_runtime.py` using their own
`__file__` path. This works with Python `-I` from another working directory and
does not add the current directory or the repository to `sys.path`.

Set `PF8_GIT` to an executable Git path when Git is outside `PATH`. For example,
`PF8_GIT=/opt/git/bin/git` selects that executable. Paths containing spaces are
passed as one subprocess argument. A command name such as `PF8_GIT=git-custom`
is looked up on `PATH`; an explicit relative path is relative to the invoking
working directory. Invalid or empty overrides fail without silently falling
back to a different executable.

When `PF8_GIT` is unset, the resolver searches the invoking environment's `PATH`
for `git`. A missing or empty `PATH` produces a clear error rather than implicitly
searching the current directory or system defaults. Resolution returns an
absolute path and checks both executable access and a successful `git --version`
response before any utility uses Git.

`git_portability_tests.py` records current test evidence in
`git_portability_results.json`. It verifies override and PATH resolution,
invalid/missing executables, isolated imports and unchanged utility logic.
The historical layout-test driver's import is stopped immediately after Git
initialization because its unguarded body would rebuild scratch packages and
replace its old report. Other utility main functions are also left unexecuted;
their historical expected revisions and results remain unchanged.
