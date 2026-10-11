#!/usr/bin/env python3
"""Test portable Git resolution and isolated utility imports on scratch files only."""
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
REVIEW = ROOT / 'verification_review_round7/independent_tool_hygiene_review.json'
SCRIPTS = [Path(item['path']) for item in next(
    finding for finding in json.loads(REVIEW.read_text())['conclusions']
    if finding['id'] == 'nine_git_literals')['scripts']]


def identity(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def main():
    resolve_git = runpy.run_path(str(HELPER))['resolve_git']
    real_git = resolve_git()
    head = subprocess.check_output([real_git, '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip()
    baseline_head = subprocess.check_output([real_git, '-C', str(ROOT), 'rev-parse', 'e7c4cd4'], text=True).strip()
    protected = [p for directory in ('verification_review_round5', 'verification_review_round6',
                                   'verification_fixes_round6', 'verification_review_round7')
                 for p in (ROOT / directory).glob('*.json')]
    protected_before = {str(p): identity(p) for p in protected}
    script_identities = [identity(p) for p in SCRIPTS]
    helper_identity = identity(HELPER)
    rows = []

    def record(name, passed, **details):
        rows.append({'name': name, 'passed': bool(passed), **details})
        if not passed:
            raise AssertionError(name + ': ' + repr(details))

    with tempfile.TemporaryDirectory(prefix='pf8_git_portability_') as temporary:
        scratch = Path(temporary)
        clean = scratch / 'clean cwd'
        clean.mkdir()
        bins = scratch / 'bin with spaces'
        bins.mkdir()

        def executable(path, body, mode=0o755):
            path.write_text('#!/bin/sh\n' + body)
            path.chmod(mode)
            return str(path)

        good = executable(bins / 'git', 'printf "%s\\n" "git version 2.0.0-test"\n')
        override = executable(scratch / 'explicit Git', 'printf "%s\\n" "git version 3.0.0-test"\n')
        bad = executable(scratch / 'not Git', 'printf "%s\\n" "not a git executable"\n')
        fail = executable(scratch / 'failed Git', 'printf "%s\\n" "git version 2.0.0-test"\nexit 7\n')
        nonexec = executable(scratch / 'nonexecutable Git', 'exit 0\n', mode=0o644)
        malformed = scratch / 'malformed executable'
        malformed.write_text('not an executable format\n')
        malformed.chmod(0o755)
        alias = scratch / 'Git symlink'
        alias.symlink_to(override)
        executable(clean / 'git', 'printf "%s\\n" "git version 9.0.0-cwd-trap"\n')
        relative = clean / 'relative Git'
        executable(relative, 'printf "%s\\n" "git version 4.0.0-test"\n')
        (bins / 'custom-git').symlink_to(override)

        probe = 'import json,runpy,sys; print(json.dumps({"git":runpy.run_path(sys.argv[1])["resolve_git"]()}))'

        def env(path, selected=None, include_override=False):
            value = os.environ.copy()
            value.pop('PF8_GIT', None)
            value.pop('PATH', None)
            if path is not None:
                value['PATH'] = path
            if include_override:
                value['PF8_GIT'] = selected
            return value

        def resolve_case(name, environment, expected=None, error=None):
            process = subprocess.run([sys.executable, '-I', '-c', probe, str(HELPER)],
                                     cwd=clean, env=environment, capture_output=True, text=True, timeout=20)
            if expected is not None:
                found = json.loads(process.stdout)['git'] if process.returncode == 0 else None
                passed = process.returncode == 0 and found == str(Path(expected).resolve())
            else:
                found = None
                passed = process.returncode != 0 and error in process.stderr
            record(name, passed, returncode=process.returncode, resolved=found,
                   diagnostic=process.stderr[-1500:] if process.returncode else '')

        resolve_case('PATH-only finds Git in directory containing spaces', env(str(bins)), expected=good)
        resolve_case('absolute override works without PATH', env(None, override, True), expected=override)
        resolve_case('override wins over another executable on PATH', env(str(bins), override, True), expected=override)
        resolve_case('override command name is resolved on PATH', env(str(bins), 'custom-git', True), expected=override)
        resolve_case('explicit relative override becomes absolute', env('', './relative Git', True), expected=relative)
        resolve_case('symlink override resolves to executable target', env('', str(alias), True), expected=override)
        resolve_case('relative PATH entry becomes absolute before subprocess cwd changes', env('../bin with spaces'), expected=good)
        resolve_case('missing PATH does not use cwd Git', env(None), error='PATH is missing or empty')
        resolve_case('empty PATH does not use cwd Git', env(''), error='PATH is missing or empty')
        resolve_case('PATH without Git fails actionably', env(str(scratch / 'empty bin')), error='Cannot resolve executable Git from PATH')
        resolve_case('missing explicit override never falls back to valid PATH',
                     env(str(bins), str(scratch / 'missing Git'), True), error='Cannot resolve executable Git from PF8_GIT')
        resolve_case('nonexecutable override fails without fallback', env(str(bins), nonexec, True), error='Cannot resolve executable Git from PF8_GIT')
        resolve_case('directory override fails without fallback', env(str(bins), str(bins), True), error='Cannot resolve executable Git from PF8_GIT')
        resolve_case('empty override is rejected', env(str(bins), '', True), error='PF8_GIT is empty')
        resolve_case('executable non-Git override is rejected', env(str(bins), bad, True), error='did not report a Git version')
        resolve_case('nonzero version command is rejected', env(str(bins), fail, True), error='exit 7')
        resolve_case('malformed executable reports execution failure', env(str(bins), str(malformed), True), error='Cannot execute Git resolved from PF8_GIT')
        wrong_bin = scratch / 'wrong bin'
        wrong_bin.mkdir()
        executable(wrong_bin / 'git', 'printf "%s\\n" "wrong program"\n')
        resolve_case('executable non-Git on PATH is rejected', env(str(wrong_bin)), error='did not report a Git version')

        # Load the actual script file from a clean cwd under -I. Eight utilities
        # have guarded main functions and are safe to import fully. The historical
        # layout-test driver has an unguarded body, so its real import stops at
        # the first subsequent line after GIT initialization, before scratch work.
        import_probe = r'''
import ast,importlib.util,json,sys
from pathlib import Path
sys.dont_write_bytecode = True
path = Path(sys.argv[1])
bounded = sys.argv[2] == 'bounded'
git_line = next(n.end_lineno for n in ast.parse(path.read_text()).body
                if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='GIT' for t in n.targets))
class BootstrapComplete(Exception): pass
def trace(frame,event,arg):
    if event == 'line' and frame.f_code.co_filename == str(path) and frame.f_lineno > git_line:
        raise BootstrapComplete()
    return trace
spec = importlib.util.spec_from_file_location('git_portability_probe',path)
module = importlib.util.module_from_spec(spec)
before = sys.path[:]
try:
    if bounded: sys.settrace(trace)
    spec.loader.exec_module(module)
except BootstrapComplete:
    pass
finally:
    sys.settrace(None)
print(json.dumps({'git':module.GIT,'root':str(module.ROOT),
                  'import_path_unchanged':sys.path==before,'bounded':bounded}))
'''
        for script in SCRIPTS:
            baseline = subprocess.check_output([real_git, '-C', str(ROOT), 'show',
                                                baseline_head + ':' + str(script.relative_to(ROOT))]).decode()
            before_tree = ast.parse(baseline)
            after_tree = ast.parse(script.read_text())
            before_git = next(n for n in before_tree.body if isinstance(n, ast.Assign)
                              and any(isinstance(t, ast.Name) and t.id == 'GIT' for t in n.targets))
            after_tree.body = [n for n in after_tree.body if not (isinstance(n, ast.Import)
                                                                and len(n.names) == 1 and n.names[0].name == 'runpy')]
            next(n for n in after_tree.body if isinstance(n, ast.Assign)
                 and any(isinstance(t, ast.Name) and t.id == 'GIT' for t in n.targets)).value = before_git.value
            record(str(script.relative_to(ROOT)) + ': only resolver wiring changes executable AST',
                   ast.dump(before_tree) == ast.dump(after_tree))
            mode = 'bounded' if script.name == 'independent_builder_layout_tests.py' else 'full'
            for selected, environment, expected in (
                ('PATH-only', env(str(bins)), good),
                ('override without PATH', env(None, override, True), override),
            ):
                process = subprocess.run([sys.executable, '-I', '-c', import_probe, str(script), mode],
                                         cwd=clean, env=environment, capture_output=True, text=True, timeout=20)
                result = json.loads(process.stdout) if process.returncode == 0 else None
                record(str(script.relative_to(ROOT)) + ': isolated import ' + selected,
                       process.returncode == 0 and result['git'] == str(Path(expected).resolve())
                       and result['root'] == str(ROOT) and result['import_path_unchanged'],
                       returncode=process.returncode, import_scope=mode, result=result,
                       diagnostic=process.stderr[-1500:] if process.returncode else '')
            process = subprocess.run([sys.executable, '-I', '-c', import_probe, str(script), mode],
                                     cwd=clean, env=env(None), capture_output=True, text=True, timeout=20)
            record(str(script.relative_to(ROOT)) + ': isolated import missing Git fails early',
                   process.returncode != 0 and 'PATH is missing or empty' in process.stderr,
                   returncode=process.returncode, diagnostic=process.stderr[-1500:])

    version = subprocess.check_output([real_git, '--version'], text=True).strip()
    record('actual resolved Git performs read-only repository query',
           subprocess.check_output([real_git, '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip() == head,
           executable=real_git, version=version)
    record('original JSON review and result evidence remains byte-identical',
           all(identity(Path(path)) == item for path, item in protected_before.items()),
           protected_count=len(protected_before))
    record('tested helper and nine utility source identities remain stable',
           identity(HELPER) == helper_identity and [identity(p) for p in SCRIPTS] == script_identities)
    result = {
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'bounded_pass', 'all_passed': all(row['passed'] for row in rows),
        'checks': len(rows), 'current_head': head, 'baseline_head': baseline_head, 'python': sys.executable,
        'helper': helper_identity, 'utilities': script_identities, 'test_driver': identity(Path(__file__).resolve()),
        'results': rows,
        'scope': 'Scratch resolver executions, read-only Git queries, AST comparison and isolated utility imports. No utility main function, scientific script, Lean artifact, server, document builder or deliverable was executed or changed by these tests.',
        'limitations': [
            'The historical independent_builder_layout_tests.py module executes its body at import; this review stops its actual import immediately after GIT initialization to avoid re-running historical package builds or overwriting evidence.',
            'Historical revision/check/finalization main functions still encode their original expected heads and inputs; portable Git discovery does not promise that those old assertions pass against later project states.',
            'Git --version validates executable identity at resolution time; later removal or replacement of the executable is outside this check.',
        ],
    }
    destination = OUT / 'git_portability_results.json'
    destination.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps({'path': str(destination), 'checks': len(rows), 'all_passed': result['all_passed']}, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
