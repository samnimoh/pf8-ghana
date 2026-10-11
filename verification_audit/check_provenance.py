#!/usr/bin/env python3
"""Read-only provenance inventory and arithmetic checks for the Pf8 manuscript.

Uses the Python standard library. It never runs analysis scripts or alters their
inputs/outputs. Only the requested JSON audit file is written. Textual markers
are diagnostic evidence, not semantic proofs that code is correct or incorrect.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import re
import sys
from datetime import datetime, timezone


DEFAULT_ROOT = Path(__file__).resolve().parent.parent
MANUSCRIPT = Path('/Users/samnimoh/Downloads/Pf8_Ghana_manuscript_REVISED.docx')


def fingerprint(path: Path) -> dict:
    record = {'path': str(path.resolve()), 'exists': path.is_file()}
    if not path.is_file():
        return record
    sha256 = hashlib.sha256()
    md5 = hashlib.md5()
    size = 0
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            size += len(block)
            sha256.update(block)
            md5.update(block)
    record.update(bytes=size, sha256=sha256.hexdigest(), md5=md5.hexdigest())
    return record


def inventory(directory: Path) -> list[dict]:
    return [fingerprint(path) for path in sorted(directory.rglob('*'))
            if path.is_file()] if directory.is_dir() else []


def csv_rows(path: Path) -> tuple[list[str], list[dict]]:
    with path.open(newline='') as stream:
        reader = csv.DictReader(stream)
        rows = list(reader)
        return list(reader.fieldnames or []), rows


def add_check(checks: list[dict], name: str, condition: bool, **evidence) -> None:
    checks.append({'name': name, 'passed': bool(condition), 'evidence': evidence})


def text_matches(path: Path, pattern: str, flags: int = 0) -> list[dict]:
    if not path.is_file():
        return []
    return [{'line': number, 'text': line.rstrip()} for number, line in
            enumerate(path.read_text().splitlines(), 1)
            if re.search(pattern, line, flags)]


def read_xtx(path: Path) -> list[float]:
    with path.open() as stream:
        header = stream.readline().split()
        column = header.index('M_XtX')
        return [float(line.split()[column]) for line in stream if line.strip()]


def linear_quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower = math.floor(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (index - lower) * (ordered[upper] - ordered[lower])


def audit(root: Path) -> dict:
    root = root.resolve()
    snapshot = root / 'evaluation/server_snapshot'
    checks: list[dict] = []
    sources = {
        'requested_downloads_manuscript': fingerprint(MANUSCRIPT),
        'different_workspace_manuscript': fingerprint(root / MANUSCRIPT.name),
        'handoff': fingerprint(root / 'HANDOFF_evaluation.md'),
        'corrections': fingerprint(root / 'CORRECTIONS_AND_NEW_RESULTS.md'),
        'proof_manifest': fingerprint(root / 'proof_of_work/MANIFEST.md'),
    }
    doc_a = sources['requested_downloads_manuscript']
    doc_b = sources['different_workspace_manuscript']
    add_check(checks, 'source_manuscripts_are_distinct',
              doc_a.get('sha256') != doc_b.get('sha256') and
              doc_a['exists'] and doc_b['exists'],
              requested_sha256=doc_a.get('sha256'), workspace_sha256=doc_b.get('sha256'))

    manifest = root / 'proof_of_work/MANIFEST.md'
    manifest_records = []
    if manifest.is_file():
        for name, size, digest in re.findall(
                r'`([^`]+)`\s+—\s+(\d+) bytes, md5 `([a-f0-9]+)`',
                manifest.read_text()):
            actual = fingerprint(root / 'proof_of_work' / name)
            matched = actual.get('bytes') == int(size) and actual.get('md5') == digest
            manifest_records.append({'file': name, 'expected_bytes': int(size),
                                     'expected_md5': digest, 'actual': actual,
                                     'matches': matched})
    add_check(checks, 'twelve_manifest_records_all_match',
              len(manifest_records) == 12 and all(r['matches'] for r in manifest_records),
              parsed_records=len(manifest_records),
              matched_records=sum(r['matches'] for r in manifest_records))

    script_inventories = {
        'v2': inventory(root / 'v2/scripts'),
        'server_snapshot': inventory(snapshot / 'scripts'),
    }
    script_comparisons = []
    for path in sorted((root / 'v2/scripts').rglob('*')):
        if not path.is_file():
            continue
        relative = path.relative_to(root / 'v2/scripts')
        peer = snapshot / 'scripts' / relative
        if peer.is_file():
            first, second = fingerprint(path), fingerprint(peer)
            script_comparisons.append({'relative_path': str(relative),
                                       'same_sha256': first['sha256'] == second['sha256'],
                                       'v2_sha256': first['sha256'],
                                       'snapshot_sha256': second['sha256']})

    textual_indicators = []
    for label, directory in [('v2', root / 'v2/scripts'),
                             ('server_snapshot', snapshot / 'scripts')]:
        entries = [
            ('step04a_prepare_callset.py',
             {'second_pass_wording': r'provisional|recomputed|two.pass',
              'variant_missingness_assignment': r'^\s*var_missing\s*=',
              'sample_missingness_assignment': r'^\s*smp_missing\s*='}),
            ('step07b_treemix.sh', {'se_option_token': r'(?<!\w)-se(?:\s|$)'}),
            ('step08c_calibrate_xtx.py',
             {'fdr_or_bh_wording': r'benjamini|hochberg|false.discovery|q_value|qvalue|\bfdr\b',
              'row_count_assertion': r'len\(positions\) != len\(obs\)'}),
            ('step05b_admixture.sh',
             {'timestamp_test_token': r'\s-nt\s', 'existence_guard': r'if \[ -f'}),
            ('step07b_treemix.sh',
             {'timestamp_test_token': r'\s-nt\s', 'completeness_guard': r'if m_complete'}),
            ('step08b_baypass.sh',
             {'timestamp_test_token': r'\s-nt\s',
              'thread_default': r'^NTHREADS=', 'existence_guard': r'if \[ -f',
              'pod_ancestral_frequency_option': r'pi\.maf'}),
            ('run_all.sh', {'exported_thread_default': r'export NTHREADS='}),
        ]
        for filename, patterns in entries:
            path = directory / filename
            textual_indicators.append({
                'snapshot': label, 'path': str(path),
                'exists': path.is_file(),
                'markers': {key: text_matches(path, value, re.IGNORECASE)
                            for key, value in patterns.items()},
                'interpretation_limit': 'Text search only; absence is not a semantic proof. '
                    'Available files are not authenticated as the scripts of the final run.',
            })

    headers, fst = csv_rows(root / 'corrected/final_fst_pairwise.csv')
    fst_max = max(fst, key=lambda row: float(row['fst']))
    zero_intervals = [row for row in fst
                      if float(row['ci95_low']) <= 0 <= float(row['ci95_high'])]
    add_check(checks, 'final_fst_six_pairs_max_and_one_zero_interval',
              len(fst) == 6 and
              math.isclose(float(fst_max['fst']), 0.0023193446574372796, abs_tol=1e-15) and
              len(zero_intervals) == 1,
              path=str(root / 'corrected/final_fst_pairwise.csv'),
              row_count=len(fst), maximum=fst_max, intervals_spanning_zero=zero_intervals)
    add_check(checks, 'final_fst_ci_arithmetic', all(
        math.isclose(float(row['ci95_low']), float(row['fst']) - 1.96 *
                     float(row['jackknife_se']), abs_tol=1e-14) and
        math.isclose(float(row['ci95_high']), float(row['fst']) + 1.96 *
                     float(row['jackknife_se']), abs_tol=1e-14) for row in fst),
        formula='fst +/- 1.96 * jackknife_se')

    final_json_path = root / 'corrected/final_xtx_calibration.json'
    final = json.loads(final_json_path.read_text())
    expected_false = final['n_snps'] * 0.001
    expected_ratio = expected_false / final['n_outliers']
    add_check(checks, 'final_baypass_summary_counts_and_arithmetic',
              final['n_snps'] == 3916 and final['n_outliers'] == 19 and
              math.isclose(final['threshold'], 10.839767826730082, abs_tol=1e-12) and
              math.isclose(final['expected_false_positives'], expected_false, abs_tol=1e-12) and
              math.isclose(final['empirical_fdr_at_threshold'], expected_ratio, abs_tol=1e-12),
              path=str(final_json_path), summary=final,
              note='Arithmetic agreement does not validate the null model or FDR control.')
    q_counts = [(row['q_threshold'], row['n_snps']) for row in final['n_by_qvalue']]
    add_check(checks, 'final_q_count_summary_matches_claims',
              q_counts == [(0.01, 8), (0.05, 10), (0.1, 13), (0.2, 17)],
              counts=q_counts,
              note='Checks summary fields only; final per-SNP p/q data are unavailable locally.')

    old_dir = snapshot / 'results/baypass'
    old_summary = json.loads((old_dir / 'xtx_calibration.json').read_text())
    old_obs = read_xtx(old_dir / 'ghana_core_summary_pi_xtx.out')
    old_pod = read_xtx(old_dir / 'ghana_pod_summary_pi_xtx.out')
    old_threshold = linear_quantile(old_pod, 0.999)
    old_outliers = sum(value > old_threshold for value in old_obs)
    old_headers, old_snps = csv_rows(old_dir / 'xtx_all_snps.csv')
    add_check(checks, 'old_baypass_raw_reproduces_old_summary',
              len(old_obs) == len(old_snps) == 3359 and len(old_pod) == 100000 and
              math.isclose(old_threshold, old_summary['threshold'], abs_tol=1e-12) and
              old_outliers == old_summary['n_outliers'] == 15,
              observed_rows=len(old_obs), pod_rows=len(old_pod),
              per_snp_table_rows=len(old_snps), per_snp_header=old_headers,
              recomputed_threshold=old_threshold, recomputed_outliers=old_outliers,
              note='This verifies the old run and cannot validate the final 3,916-SNP scan.')

    sample_path = snapshot / 'interim/analysis_samples.csv'
    _, samples = csv_rows(sample_path)
    zone_counts: dict[str, int] = {}
    for sample in samples:
        zone_counts[sample['zone']] = zone_counts.get(sample['zone'], 0) + 1
    add_check(checks, 'sample_table_has_1900_and_expected_zone_counts',
              len(samples) == 1900 and zone_counts == {
                  'Guinea savanna': 1334, 'Decidous forest': 337,
                  'Coastal savanna': 204, 'Transitional zone': 25},
              path=str(sample_path), rows=len(samples), zone_counts=zone_counts)

    output_inventories = {name: inventory(root / name)
                         for name in ['corrected', 'proof_of_work']}
    local_output_files = [p for directory in [root / 'corrected', root / 'proof_of_work',
                                              root / 'pf8_proof', snapshot]
                          for p in directory.rglob('*') if p.is_file()]
    availability = {}
    for name in ['ghana_core_snps.npz', 'ghana_baypass.geno',
                 'ghana_core_summary_pi_xtx.out', 'ghana_pod_summary_pi_xtx.out',
                 'xtx_all_snps.csv', 'rerun_corrected.log', 'rerun_5to9.log',
                 'step12_codon_panel.py', 'step13_sensitivity.py']:
        availability[name] = [str(p) for p in local_output_files if p.name == name]
    availability['final_treeout_files'] = [str(p) for p in local_output_files
        if re.fullmatch(r'treemix_m\d+\.treeout\.gz', p.name) and
        'server_snapshot' not in p.parts]

    return {
        'schema_version': 1,
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'python_executable': sys.executable,
        'workspace_root': str(root),
        'scope': 'Read-only local inventories, hashes, text markers and arithmetic. '
                 'No remote connection, pipeline execution, input mutation or manuscript substitution.',
        'sources': sources,
        'manifest_verification': manifest_records,
        'script_file_hashes': script_inventories,
        'script_snapshot_comparisons': script_comparisons,
        'script_textual_indicators': textual_indicators,
        'corrected_and_proof_file_hashes': output_inventories,
        'checks': checks,
        'check_summary': {'passed': sum(check['passed'] for check in checks),
                          'total': len(checks)},
        'output_availability': availability,
        'provenance_limits': [
            'Final results CSV/JSON files and manually extracted log text are available; '
            'full final generating scripts, genotype matrix, BayPass raw XtX/POD files and '
            'original final TreeMix outputs cannot be traced from this local bundle.',
            'Available v2 and server_snapshot scripts contain earlier code. Their absence '
            'of claimed final corrections does not prove the remote final run lacked those fixes.',
            'Final p/q values and AAT1 q=0.0049 cannot be independently recomputed from '
            'available local raw data. Available per-SNP data describe the old 3,359-SNP run.',
            'Manifest matches verify integrity against the supplied manifest, not remote origin '
            'or biological/statistical validity.',
            'Later corrected workspace outputs address several unperformed analyses in the '
            'requested Downloads manuscript; their generating step12/step13 scripts are absent.',
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=DEFAULT_ROOT)
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).resolve().parent / 'provenance_validation.json')
    args = parser.parse_args()
    result = audit(args.root)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'output': str(args.output.resolve()),
                      'checks': result['check_summary'],
                      'manifest_records': len(result['manifest_verification']),
                      'script_files_hashed': sum(map(len, result['script_file_hashes'].values())),
                      'outputs_hashed': sum(map(len, result['corrected_and_proof_file_hashes'].values())),
                      'final_raw_provenance': 'incomplete'}))
    if not all(check['passed'] for check in result['checks']):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
