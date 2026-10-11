#!/usr/bin/env python3
"""Run the local Pf8 checkers and compile the reference proofs with Lean 4.19.0.

No installation or network access is performed. The three Python checkers run
sequentially under this interpreter. Lean compilation and printed dependencies
verify the saved reference specifications, not refinement of the entire pipeline.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys


AUDIT_DIR = Path(__file__).resolve().parent
PINNED_LEAN_VERSION = '4.19.0'
EXPECTED_THEOREM_COUNT = 16
ALLOWED_AXIOMS = {'propext', 'Classical.choice', 'Quot.sound'}
PYTHON_CHECKERS = ('check_provenance.py', 'check_majority_script.py',
                   'check_marker_outputs.py')


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def remove_lean_comments(source: str) -> str:
    """Remove nested block and line comments while preserving quoted strings."""
    out = []
    index = 0
    block_depth = 0
    in_string = False
    while index < len(source):
        char = source[index]
        pair = source[index:index + 2]
        if block_depth:
            if pair == '/-':
                block_depth += 1
                out.append('  ')
                index += 2
            elif pair == '-/':
                block_depth -= 1
                out.append('  ')
                index += 2
            else:
                out.append('\n' if char == '\n' else ' ')
                index += 1
        elif in_string:
            out.append(char)
            index += 1
            if char == '\\' and index < len(source):
                out.append(source[index])
                index += 1
            elif char == '"':
                in_string = False
        elif pair == '/-':
            block_depth = 1
            out.append('  ')
            index += 2
        elif pair == '--':
            end = source.find('\n', index)
            if end == -1:
                out.append(' ' * (len(source) - index))
                break
            out.append(' ' * (end - index))
            index = end
        else:
            out.append(char)
            in_string = char == '"'
            index += 1
    return ''.join(out)


def command_result(command: list[str], timeout: int) -> dict:
    record = {'command': command, 'cwd': str(AUDIT_DIR)}
    try:
        result = subprocess.run(command, cwd=AUDIT_DIR, capture_output=True,
                                text=True, timeout=timeout, check=False)
        record.update(exit_code=result.returncode, stdout=result.stdout,
                      stderr=result.stderr, status='completed')
    except subprocess.TimeoutExpired as error:
        def as_text(value):
            return value.decode(errors='replace') if isinstance(value, bytes) else value or ''
        record.update(exit_code=None, stdout=as_text(error.stdout),
                      stderr=as_text(error.stderr), status='timeout')
    except OSError as error:
        record.update(exit_code=None, stdout='', stderr=str(error), status='unavailable')
    return record


def parsed_axiom_reports(output: str) -> list[dict]:
    # #print axioms normally uses single-quoted declaration names. Accept the
    # unquoted form too, and allow a multiline dependency list.
    pattern = re.compile(
        r"(?:'([^']+)'|([A-Za-z_][A-Za-z0-9_'.]*))\s+"
        r'(?:does not depend on any axioms|depends on axioms:\s*\[([^\]]*)\])'
    )
    records = []
    for match in pattern.finditer(output):
        name = match.group(1) or match.group(2)
        dependencies = [part.strip() for part in (match.group(3) or '').split(',')
                        if part.strip()]
        records.append({'name': name, 'dependencies': dependencies,
                        'unexpected_dependencies': sorted(set(dependencies) - ALLOWED_AXIOMS),
                        'raw_output': match.group(0)})
    return records


def log_section(label: str, record: dict) -> str:
    return (f'[{label}]\ncommand: {json.dumps(record["command"])}\n'
            f'status: {record["status"]}; exit_code: {record["exit_code"]}\n'
            f'--- stdout ---\n{record["stdout"]}\n'
            f'--- stderr ---\n{record["stderr"]}\n')


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lean', default=shutil.which('lean'),
                        help='Lean executable; default: lean found on PATH.')
    parser.add_argument('--timeout', type=int, default=60,
                        help='Maximum seconds for each subprocess (default: 60).')
    args = parser.parse_args()
    if args.timeout < 1:
        parser.error('--timeout must be positive')

    source = AUDIT_DIR / 'Pf8Audit.lean'
    olean = AUDIT_DIR / 'Pf8Audit.olean'
    log_path = AUDIT_DIR / 'lean_check.log'
    json_path = AUDIT_DIR / 'lean_validation.json'
    original_hash = sha256(source)
    code = remove_lean_comments(source.read_text())
    theorem_names = re.findall(r'^\s*theorem\s+([A-Za-z_][A-Za-z0-9_]*)', code,
                               flags=re.MULTILINE)
    print_targets = re.findall(r'^\s*#print\s+axioms\s+([A-Za-z_][A-Za-z0-9_.]*)', code,
                               flags=re.MULTILINE)
    forbidden_proof_tokens = sorted(set(re.findall(r'\b(?:sorry|admit|native_decide)\b', code)))
    custom_axiom_declarations = re.findall(
        r'^\s*(?:(?:private|protected)\s+)?axiom\s+([^\s:(]+)', code,
        flags=re.MULTILINE)

    checkers = []
    log_parts = []
    for filename in PYTHON_CHECKERS:
        result = command_result([sys.executable, str(AUDIT_DIR / filename)], args.timeout)
        result['checker'] = filename
        checkers.append(result)
        log_parts.append(log_section(filename, result))
        print(f'{filename}: {result["status"]}, exit={result["exit_code"]}', flush=True)

    version_result = None
    compile_result = None
    compiler_version = None
    lean_status = 'unavailable'
    axiom_reports = []
    if args.lean:
        lean_executable = str(Path(args.lean).expanduser().resolve())
        version_result = command_result([lean_executable, '--version'], args.timeout)
        log_parts.append(log_section('Lean version', version_result))
        match = re.search(r'\bversion\s+([^,\s)]+)', version_result['stdout'])
        compiler_version = match.group(1) if match else None
        if version_result['exit_code'] != 0:
            lean_status = version_result['status']
        elif compiler_version != PINNED_LEAN_VERSION:
            lean_status = 'version_mismatch'
        else:
            compile_result = command_result(
                [lean_executable, '-o', str(olean), str(source)], args.timeout)
            log_parts.append(log_section('Lean compile', compile_result))
            axiom_reports = parsed_axiom_reports(
                compile_result['stdout'] + '\n' + compile_result['stderr'])
            lean_status = 'compiled' if compile_result['exit_code'] == 0 else 'compile_failed'
    else:
        lean_executable = None
        log_parts.append('[Lean unavailable]\nNo --lean path supplied and lean is not on PATH.\n')

    printed_short_names = [record['name'].rsplit('.', 1)[-1] for record in axiom_reports]
    unexpected_axioms = sorted({name for report in axiom_reports
                               for name in report['unexpected_dependencies']})
    validation_checks = {
        'python_checkers_passed': all(record['exit_code'] == 0 for record in checkers),
        'compiler_exactly_pinned': compiler_version == PINNED_LEAN_VERSION,
        'lean_compile_succeeded': compile_result is not None and compile_result['exit_code'] == 0,
        'olean_output_exists': olean.is_file() if compile_result and compile_result['exit_code'] == 0 else False,
        'source_unchanged': sha256(source) == original_hash,
        'sixteen_source_theorems': len(theorem_names) == EXPECTED_THEOREM_COUNT,
        'sixteen_axiom_print_requests': len(print_targets) == EXPECTED_THEOREM_COUNT,
        'print_requests_cover_source_theorems': sorted(target.rsplit('.', 1)[-1]
            for target in print_targets) == sorted(theorem_names),
        'sixteen_compiler_axiom_reports': len(axiom_reports) == EXPECTED_THEOREM_COUNT,
        'compiler_reports_cover_source_theorems': sorted(printed_short_names) == sorted(theorem_names),
        'only_allowed_standard_axioms': not unexpected_axioms and
                                      len(axiom_reports) == EXPECTED_THEOREM_COUNT,
        'no_forbidden_proof_tokens_outside_comments': not forbidden_proof_tokens,
        'no_custom_axiom_declarations_outside_comments': not custom_axiom_declarations,
    }
    passed = all(validation_checks.values())
    result = {
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'passed' if passed else 'failed',
        'lean_status': lean_status,
        'python_executable': sys.executable,
        'python_checker_results': checkers,
        'pinned_lean_version': PINNED_LEAN_VERSION,
        'lean_executable': lean_executable,
        'compiler_version': compiler_version,
        'compiler_version_command': version_result,
        'compiler_result': compile_result,
        'source_path': str(source),
        'source_sha256': original_hash,
        'olean_path': str(olean),
        'olean_sha256': sha256(olean) if compile_result and compile_result['exit_code'] == 0
                        and olean.is_file() else None,
        'theorem_names': theorem_names,
        'theorem_count': len(theorem_names),
        'axiom_print_targets': print_targets,
        'axiom_report_count': len(axiom_reports),
        'axiom_reports': axiom_reports,
        'allowed_standard_axioms': sorted(ALLOWED_AXIOMS),
        'unexpected_dependency_names': unexpected_axioms,
        'forbidden_proof_tokens_outside_comments': forbidden_proof_tokens,
        'custom_axiom_declarations_outside_comments': custom_axiom_declarations,
        'checks': validation_checks,
        'log_path': str(log_path),
        'limitations': [
            'Lean establishes the reference theorem statements, not formal refinement of the '
            'Python implementation, model calibration, source-data correctness or national prevalence.',
            'The Python checkers perform the finite checks and provenance audits described in their logs.',
            'Unapproved dependency names are rejected by an explicit allowlist; ordinary propext, '
            'Classical.choice and Quot.sound are permitted. Comments are excluded from token checks.',
        ],
    }
    log_parts.append('[Validation checks]\n' + json.dumps(validation_checks, indent=2) + '\n')
    log_path.write_text('\n'.join(log_parts))
    json_path.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(f'Verification {result["status"]}; Lean={lean_status}; '
          f'theorems={len(theorem_names)}; axiom_reports={len(axiom_reports)}', flush=True)
    print(f'Log: {log_path}\nJSON: {json_path}')
    raise SystemExit(0 if passed else 1)


if __name__ == '__main__':
    main()
