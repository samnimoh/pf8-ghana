#!/usr/bin/env python3
"""Independent bounded Git bootstrap probes; no utility main body is run."""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
HELPER = ROOT / 'tools/git_runtime.py'
SCRIPTS = [ROOT / p for p in (
    'verification_review_round5/check_current_revision.py',
    'verification_review_round5/finalize_review.py',
    'verification_review_round6/check_current_revision.py',
    'verification_review_round6/finalize_review.py',
    'verification_fixes_round6/independent_builder_layout_tests.py',
    'verification_fixes_round6/make_fix_manifest.py',
    'verification_fixes_round6/verify_documents.py',
    'verification_fixes_round6/final_document_review_checker.py',
    'verification_fixes_round6/final_closure_review_checker.py',
)]


def identity(path):
    b = path.read_bytes()
    return dict(path=str(path), bytes=len(b), sha256=hashlib.sha256(b).hexdigest())


def main():
    checks = []
    inputs = [HELPER, *SCRIPTS, OUT / 'git_portability_tests.py', OUT / 'git_portability_results.json']
    before = [identity(p) for p in inputs]
    protected = [p for folder in ('verification_review_round5', 'verification_review_round6',
                                 'verification_fixes_round6', 'verification_review_round7')
                 for p in (ROOT / folder).glob('*.json')]
    protected_before = [identity(p) for p in protected]
    real_git = runpy.run_path(str(HELPER))['resolve_git']()
    baseline = subprocess.check_output([real_git, '-C', str(ROOT), 'rev-parse', '64515dc'], text=True).strip()

    def check(name, passed, **evidence):
        checks.append(dict(name=name, passed=bool(passed), **evidence))
        if not passed:
            raise AssertionError(name + ': ' + repr(evidence))

    with tempfile.TemporaryDirectory(prefix='pf8_independent_git_') as scratch_name:
        scratch = Path(scratch_name)
        cwd = scratch / 'unrelated cwd'
        cwd.mkdir()
        (cwd / 'shutil.py').write_text('raise RuntimeError("CWD_MODULE_IMPORTED")\n')
        (cwd / 'git_runtime.py').write_text('raise RuntimeError("CWD_HELPER_IMPORTED")\n')
        bins = scratch / 'bin'
        bins.mkdir()
        good = bins / 'git'
        good.write_text('#!/bin/sh\nprintf "%s\\n" "git version independent-probe"\n')
        good.chmod(0o755)
        odd = cwd / "git '$; literal"
        odd.write_bytes(good.read_bytes())
        odd.chmod(0o755)
        malformed = scratch / 'malformed stdout'
        malformed.write_text("#!/bin/sh\nprintf '\\377'\n")
        malformed.chmod(0o755)
        broken = scratch / 'broken Git link'
        broken.symlink_to(scratch / 'absent target')
        marker = scratch / 'shell-injection-marker'

        def env(path=None, override=None, set_override=False):
            result = os.environ.copy()
            result.pop('PATH', None)
            result.pop('PF8_GIT', None)
            if path is not None:
                result['PATH'] = path
            if set_override:
                result['PF8_GIT'] = override
            return result

        resolver_probe = r'''
import json,os,runpy,subprocess,sys
m=runpy.run_path(sys.argv[1])
if sys.argv[2]=='timeout':
    def fail(*a,**kw): raise subprocess.TimeoutExpired(a[0],kw['timeout'])
    m['resolve_git'].__globals__['subprocess'].run=fail
git=m['resolve_git']()
if sys.argv[2]=='change-cwd':
    os.chdir(sys.argv[3])
    assert subprocess.check_output([git,'--version'],text=True).startswith('git version ')
print(json.dumps({'git':git,'isolated':bool(sys.flags.isolated)}))
'''

        def resolve(name, environment, expected=None, error=None, mode='normal'):
            p = subprocess.run([sys.executable, '-I', '-c', resolver_probe, str(HELPER), mode, str(scratch)],
                               cwd=cwd, env=environment, capture_output=True, text=True, timeout=20)
            data = json.loads(p.stdout) if p.returncode == 0 else None
            passed = (p.returncode == 0 and data['git'] == str(Path(expected).resolve()) and data['isolated']) if expected else (
                p.returncode != 0 and error in p.stderr and 'CWD_MODULE_IMPORTED' not in p.stderr)
            check(name, passed, returncode=p.returncode, result=data, diagnostic=p.stderr[-1200:])

        resolve('absolute override bypasses absent PATH and cwd traps', env(override=str(odd), set_override=True), expected=odd)
        resolve('literal quote dollar semicolon path is one executable argument', env('', str(odd), True), expected=odd)
        check('literal special-character executable name has no shell side effect', not marker.exists())
        resolve('relative override survives subsequent cwd change', env('', './'+odd.name, True), expected=odd, mode='change-cwd')
        resolve('relative PATH result survives subsequent cwd change', env('../bin'), expected=good, mode='change-cwd')
        resolve('broken explicit symlink does not use valid PATH fallback', env(str(bins), str(broken), True), error='Cannot resolve executable Git from PF8_GIT')
        resolve('bare explicit name cannot use missing PATH default', env(override='git', set_override=True), error='PATH is missing or empty')
        resolve('malformed stdout is caught as actionable execution error', env('', str(malformed), True), error='Cannot execute Git resolved from PF8_GIT')
        resolve('timeout branch is caught as actionable execution error', env('', str(good), True), error='Cannot execute Git resolved from PF8_GIT', mode='timeout')

        # Execute the real module initialization through its GIT assignment,
        # then stop before any historical utility body or output can run.
        bootstrap_probe = r'''
import ast,importlib.util,json,sys
from pathlib import Path
sys.dont_write_bytecode=True
path=Path(sys.argv[1])
line=next(n.end_lineno for n in ast.parse(path.read_text()).body if isinstance(n,ast.Assign)
          and any(isinstance(t,ast.Name) and t.id=='GIT' for t in n.targets))
class StopBootstrap(Exception): pass
def trace(frame,event,arg):
    if event=='line' and frame.f_code.co_filename==str(path) and frame.f_lineno>line:
        raise StopBootstrap()
    return trace
spec=importlib.util.spec_from_file_location('independent_bootstrap_probe',path)
module=importlib.util.module_from_spec(spec)
before=sys.path[:]
try:
    sys.settrace(trace)
    spec.loader.exec_module(module)
except StopBootstrap:
    pass
finally:
    sys.settrace(None)
print(json.dumps({'git':module.GIT,'root':str(module.ROOT),'unchanged_sys_path':before==sys.path,
                  'isolated':bool(sys.flags.isolated)}))
'''
        for script in SCRIPTS:
            relative = str(script.relative_to(ROOT))
            original = ast.parse(subprocess.check_output([real_git, '-C', str(ROOT), 'show', baseline+':'+relative], text=True))
            current = ast.parse(script.read_text())
            original_git = next(n for n in original.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'GIT' for t in n.targets))
            current.body = [n for n in current.body if not (isinstance(n, ast.Import) and len(n.names) == 1 and n.names[0].name == 'runpy')]
            next(n for n in current.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'GIT' for t in n.targets)).value = original_git.value
            check(relative+': executable AST outside Git bootstrap unchanged', ast.dump(original) == ast.dump(current))
            for variant, environment, expected in (
                ('PATH', env(str(bins)), good),
                ('explicit override no PATH', env(override=str(odd), set_override=True), odd),
            ):
                p = subprocess.run([sys.executable, '-I', '-c', bootstrap_probe, str(script)], cwd=cwd,
                                   env=environment, capture_output=True, text=True, timeout=20)
                data = json.loads(p.stdout) if p.returncode == 0 else None
                check(relative+': isolated unrelated cwd bootstrap '+variant,
                      p.returncode == 0 and data == dict(git=str(expected.resolve()), root=str(ROOT), unchanged_sys_path=True, isolated=True),
                      returncode=p.returncode, result=data, diagnostic=p.stderr[-1200:])
            p = subprocess.run([sys.executable, '-I', '-c', bootstrap_probe, str(script)], cwd=cwd,
                               env=env(), capture_output=True, text=True, timeout=20)
            check(relative+': missing Git fails before post-bootstrap work',
                  p.returncode != 0 and 'PATH is missing or empty' in p.stderr,
                  returncode=p.returncode, diagnostic=p.stderr[-1200:])

    check('helper utilities and primary portability evidence unchanged', before == [identity(p) for p in inputs])
    check('all protected historical JSON evidence unchanged', protected_before == [identity(p) for p in protected], count=len(protected))
    result = dict(generated_utc=datetime.now(timezone.utc).isoformat(), status='bounded_pass',
                  checks=len(checks), all_passed=all(row['passed'] for row in checks), python=sys.executable,
                  baseline=baseline, reviewed_inputs=before, driver=identity(Path(__file__).resolve()), results=checks,
                  scope='Independent scratch executables, isolated real-script bootstrap only, read-only Git and AST comparison. No main function, document builder, deliverable or scientific analysis executed.',
                  limits=['Bootstrap probes deliberately stop every utility immediately after Git initialization.',
                          'Historical main functions retain their original expected revisions and inputs.',
                          'A successful version prefix is a suitability check, not cryptographic executable authentication; later executable replacement is outside scope.'])
    target = OUT / 'independent_git_probe_results.json'
    target.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(dict(path=str(target), checks=len(checks), all_passed=result['all_passed'])))


if __name__ == '__main__':
    main()
