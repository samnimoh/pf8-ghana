#!/usr/bin/env python3
"""Independently inspect the newly supplied final BayPass/TreeMix artifacts.

Standard library only. Never executes analysis scripts, connects to the server,
changes baseline verification files, or edits provenance_final. Writes one JSON
report in verification_review. Supplied verification notes are evidence to test.
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
import statistics
import sys


ROOT = Path(__file__).resolve().parent.parent


def digest(path: Path) -> dict:
    payload = path.read_bytes()
    return {'path': str(path.resolve()), 'bytes': len(payload),
            'sha256': hashlib.sha256(payload).hexdigest(),
            'md5': hashlib.md5(payload).hexdigest()}


def read_csv(path: Path, delimiter=',') -> list[dict]:
    with path.open(newline='') as stream:
        return list(csv.DictReader(stream, delimiter=delimiter))


def inventory(directory: Path) -> list[dict]:
    return [digest(path) for path in sorted(directory.rglob('*')) if path.is_file()]


def bh_adjust(pvalues: list[float]) -> list[float]:
    count = len(pvalues)
    order = sorted(range(count), key=pvalues.__getitem__)
    adjusted = [0.0] * count
    running = 1.0
    for position in range(count - 1, -1, -1):
        index = order[position]
        running = min(running, count * pvalues[index] / (position + 1))
        adjusted[index] = running
    return adjusted


def parse_treeout(path: Path) -> tuple[list[dict], list[dict]]:
    model = None
    edges = []
    trees = []
    per_model_counts: dict[int, int] = {}
    for line_number, raw in enumerate(path.read_text().splitlines(), 1):
        if raw.startswith('== m='):
            model = int(raw.rsplit('=', 1)[1])
        elif raw.startswith('('):
            trees.append({'m': model, 'line': line_number, 'newick': raw})
        elif raw.strip():
            fields = raw.split()
            weight, mean, se = map(float, fields[:3])
            per_model_counts[model] = per_model_counts.get(model, 0) + 1
            z = mean / se
            stable_tail = 0.5 * math.erfc(z / math.sqrt(2))
            naive_tail = 1.0 - 0.5 * (1.0 + math.erf(z / math.sqrt(2)))
            censored = fields[3].startswith('<')
            printed_value = float(fields[3].lstrip('<'))
            edges.append({
                'm': model, 'edge': per_model_counts[model], 'line': line_number,
                'weight': weight, 'jackknife_mean': mean, 'jackknife_se': se,
                'printed_p_token': fields[3], 'printed_p_value_or_bound': printed_value,
                'p_is_censored': censored, 'z_from_printed_mean_and_se': z,
                'stable_one_sided_normal_tail': stable_tail,
                'naive_one_minus_cdf_tail': naive_tail,
                'printed_point_relative_error': None if censored else
                    abs(printed_value - stable_tail) / stable_tail,
                'matches_three_significant_figures': not censored and
                    format(printed_value, '.3g') == format(stable_tail, '.3g'),
                'printed_bound_contains_computed_tail':
                    stable_tail < printed_value if censored else None,
                'conditional_significant_at_005_from_stable_tail': stable_tail < 0.05,
                'origin_and_destination': fields[4:],
            })
    return edges, trees


def choose_model(rows: list[dict], lower: int, upper: int, threshold: float,
                 plateau_tolerance: float = 0.001) -> int:
    subset = sorted((row for row in rows if lower <= int(row['m']) <= upper),
                    key=lambda row: int(row['m']))
    above = [int(row['m']) for row in subset
             if float(row['variance_explained']) >= threshold]
    if above:
        return min(above)
    best = max(float(row['variance_explained']) for row in subset)
    return min(int(row['m']) for row in subset
               if float(row['variance_explained']) >= best - plateau_tolerance)


def residual_summary(path: Path, explained: float) -> dict:
    with path.open(newline='') as stream:
        rows = list(csv.reader(stream))
    labels = rows[0][1:]
    matrix = [[float(value) for value in row[1:]] for row in rows[1:]]
    off_diagonal = [matrix[i][j] for i in range(len(matrix))
                    for j in range(i + 1, len(matrix))]
    residual_variance = statistics.pvariance(off_diagonal)
    return {
        'path': str(path), 'labels': labels,
        'row_labels': [row[0] for row in rows[1:]],
        'symmetric': all(matrix[i][j] == matrix[j][i] for i in range(len(matrix))
                         for j in range(len(matrix))),
        'unique_off_diagonal_residuals': off_diagonal,
        'off_diagonal_population_variance': residual_variance,
        'implied_observed_variance': residual_variance / (1 - explained),
        'limit': 'Checks consistency across models; the actual final observed '
                 'covariance and covariance standard errors are not supplied.',
    }


def audit(root: Path) -> dict:
    package = root / 'provenance_final'
    results = package / 'results'
    baseline = root / 'verification_audit'
    before_hashes = inventory(baseline)
    inputs = inventory(package)
    checks = []

    def check(name, passed, **evidence):
        checks.append({'name': name, 'passed': bool(passed), 'evidence': evidence})

    table_path = results / 'xtx_all_snps.csv'
    rows = read_csv(table_path)
    pvalues = [float(row['pval_pod']) for row in rows]
    qvalues = [float(row['qvalue']) for row in rows]
    xtx = [float(row['xtx']) for row in rows]
    recomputed_q = bh_adjust(pvalues)
    q_differences = [abs(a - b) for a, b in zip(qvalues, recomputed_q)]
    q_counts = {str(level): sum(q <= level for q in qvalues)
                for level in (0.01, 0.05, 0.10, 0.20)}
    previous_summary = json.loads((root / 'corrected/final_xtx_calibration.json').read_text())
    threshold = previous_summary['threshold']
    flags = [row['is_outlier'] == 'True' for row in rows]
    check('final_snp_table_size_ids_and_coordinates', len(rows) == 3916 and
          [int(row['baypass_row']) for row in rows] == list(range(3916)) and
          len({(row['chrom'], row['pos']) for row in rows}) == 3916,
          rows=len(rows), header=list(rows[0]), unique_coordinates=
          len({(row['chrom'], row['pos']) for row in rows}))
    check('table_md5_matches_supplied_notes', digest(table_path)['md5'] ==
          '14ee58aba477e1d229300a6c60aa02f0',
          measured_md5=digest(table_path)['md5'],
          limitation='Verifies the stated local checksum; remote byte identity is not independently checked.')
    check('bh_adjustment_reproduces_all_saved_qvalues', max(q_differences) <= 1e-12,
          maximum_absolute_difference=max(q_differences),
          mismatching_rows=[i for i, delta in enumerate(q_differences) if delta > 1e-12])
    check('q_counts_match_previous_final_summary', q_counts ==
          {'0.01': 8, '0.05': 10, '0.1': 13, '0.2': 17}, counts=q_counts)
    check('quantile_outlier_flags_match_previous_final_threshold',
          all(flag == (value > threshold) for flag, value in zip(flags, xtx)) and
          sum(flags) == previous_summary['n_outliers'] == 19,
          threshold_source=str(root / 'corrected/final_xtx_calibration.json'),
          threshold=threshold, outliers=sum(flags),
          fdr_expected_count_ratio=3916 * 0.001 / sum(flags))
    check('saved_p_and_qvalues_obey_basic_bounds', all(
        0 < p <= q <= 1 for p, q in zip(pvalues, qvalues)))
    lattice_errors = [abs(p * 100001 - round(p * 100001)) for p in pvalues]
    check('pvalues_compatible_with_100000_plus_one_tail_lattice',
          max(lattice_errors) < 1e-8 and min(pvalues) >= 1 / 100001,
          assumed_pod_count=100000, maximum_integer_lattice_error=max(lattice_errors),
          p_floor=1 / 100001, number_at_floor=sum(
              math.isclose(p, 1 / 100001, abs_tol=1e-15) for p in pvalues),
          limitation='Lattice compatibility does not verify the simulated null or actual tail ranks.')
    order = sorted(range(len(rows)), key=xtx.__getitem__)
    monotone = all(pvalues[order[i]] >= pvalues[order[i + 1]] - 1e-15
                   for i in range(len(order) - 1))
    check('saved_pvalues_monotone_with_xtx', monotone)
    selected_positions = {('Pf3D7_06_v3', '1214350'), ('Pf3D7_06_v3', '1215233'),
                          ('Pf3D7_11_v3', '1054078'), ('Pf3D7_11_v3', '1054447')}
    selected_rows = [{'source_line': i + 2, **row} for i, row in enumerate(rows)
                     if (row['chrom'], row['pos']) in selected_positions]

    tree_path = results / 'treemix_treeout_all.txt'
    edges, trees = parse_treeout(tree_path)
    check('treeout_contains_six_models_and_expected_edge_counts',
          [tree['m'] for tree in trees] == list(range(6)) and all(
              sum(edge['m'] == m for edge in edges) == m for m in range(6)),
          tree_models=[tree['m'] for tree in trees], edge_count=len(edges))
    extracts = (root / 'proof_of_work/RAW_LOG_EXTRACTS.txt').read_text().splitlines()
    old_extract_edges = []
    model = None
    for line in extracts:
        model_match = re.match(r'\s*m=(\d+):', line)
        if model_match:
            model = int(model_match.group(1))
        elif re.match(r'^\s*\d+\.\d+\s+\d+\.\d+\s+\d+\.\d+\s+<?\d', line):
            old_extract_edges.append((model, line.split()[:4]))
    new_extract_edges = [(edge['m'], [str(edge['weight']), str(edge['jackknife_mean']),
                                      str(edge['jackknife_se']), edge['printed_p_token']])
                         for edge in edges if edge['m'] <= 3]
    # Compare numeric values, not lexical float formatting.
    extract_agreement = len(old_extract_edges) == len(new_extract_edges) == 6
    for (old_m, old), (new_m, new) in zip(old_extract_edges, new_extract_edges):
        extract_agreement &= old_m == new_m and all(
            float(old[j]) == float(new[j]) for j in range(3)) and old[3] == new[3]
    check('new_treeout_reproduces_previous_final_edge_extracts', extract_agreement,
          extract_rows=len(old_extract_edges), comparison_rows=len(new_extract_edges))

    model_rows = read_csv(results / 'model_comparison.csv')
    selection = json.loads((results / 'model_selection.json').read_text())
    restricted_pick = choose_model(model_rows, 0, 2, selection['variance_explained_threshold'])
    full_pick = choose_model(model_rows, 0, 5, selection['variance_explained_threshold'])
    check('saved_heuristic_model_selections_reproduce', restricted_pick ==
          selection['identifiable_range']['m'] == 2 and full_pick ==
          selection['full_range']['m'] == 3,
          restricted_range_pick=restricted_pick, full_range_pick=full_pick,
          limitation='Confirms the numerical heuristic, not graph identifiability or exactly two historical edges.')
    likelihood = read_csv(results / 'likelihood_by_m.tsv', delimiter='\t')
    status = read_csv(results / 'run_status.tsv', delimiter='\t')
    check('model_likelihood_and_status_tables_agree', len(likelihood) == len(status) ==
          len(model_rows) == 6 and all(
              int(a['m']) == int(b['m']) and float(a['log_likelihood']) ==
              float(b['log_likelihood']) for a, b in zip(model_rows, likelihood)) and all(
              row['status'] == 'ok' and row['exit_code'] == '0' for row in status))
    residuals = {str(m): residual_summary(results / f'residuals_m{m}.csv',
                 float(next(row['variance_explained'] for row in model_rows
                            if int(row['m']) == m))) for m in (2, 3)}
    check('residual_matrices_and_explained_variance_are_consistent',
          all(row['symmetric'] and row['labels'] == row['row_labels']
              for row in residuals.values()) and math.isclose(
              residuals['2']['implied_observed_variance'],
              residuals['3']['implied_observed_variance'], rel_tol=1e-9),
          m2_implied_observed_variance=residuals['2']['implied_observed_variance'],
          m3_implied_observed_variance=residuals['3']['implied_observed_variance'])

    first_six = [edge for edge in edges if edge['m'] <= 3]
    errors = [edge for edge in edges if edge['p_is_censored'] or
              edge['printed_point_relative_error'] > 0.005]
    unresolved_names = ['ghana_core_summary_pi_xtx.out', 'ghana_pod_summary_pi_xtx.out',
                        'step08c_calibrate_xtx.py', 'step08b_baypass.sh',
                        'step07b_treemix.sh', 'step04a_prepare_callset.py', 'run_all.sh',
                        'ghana_core_snps.npz', 'rerun_corrected.log']
    supplied_availability = {name: [str(path) for path in package.rglob(name)]
                             for name in unresolved_names}
    after_hashes = inventory(baseline)
    check('baseline_verification_files_unchanged', before_hashes == after_hashes,
          files_checked=len(before_hashes))
    return {
        'generated_utc': datetime.now(timezone.utc).isoformat(),
        'python_executable': sys.executable,
        'scope': 'Independent local arithmetic, file integrity and cross-artifact checks. '
                 'No pipeline or server execution; originals and baseline preserved.',
        'input_hashes': inputs,
        'baseline_file_hashes': before_hashes,
        'checks': checks,
        'check_summary': {'passed': sum(check['passed'] for check in checks), 'total': len(checks)},
        'baypass': {
            'selected_variant_rows': selected_rows,
            'xtx_range': [min(xtx), max(xtx)], 'xtx_median': statistics.median(xtx),
            'q_counts': q_counts, 'maximum_recomputed_q_difference': max(q_differences),
            'resolved': ['Final per-SNP XtX, saved p-values, q-values and outlier flags are now local.',
                         'BH adjustment, all published q-counts and AAT1 q-values reproduce.'],
            'open': ['Final raw POD/core summaries and final calibration/preprocessing scripts '
                     'are not supplied. Saved p-values and threshold cannot be independently '
                     'regenerated from the fitted simulated null.',
                     'BH agreement does not establish null calibration, FDR control or '
                     'biological selection. MAF/model adequacy concerns remain.'],
        },
        'treemix': {
            'models': model_rows, 'selection': selection,
            'trees': trees, 'edge_probability_recomputations': edges,
            'residual_consistency': residuals,
            'first_six_edges_matching_three_significant_figures': sum(
                edge['matches_three_significant_figures'] for edge in first_six),
            'first_six_edge_count': len(first_six),
            'numerically_discrepant_edges': errors,
            'resolved': ['Final concatenated trees and jackknife statistics are now available '
                         'and agree with earlier extracted final statistics.',
                         'Stored heuristic model choice reproduces: m=3 on full range, '
                         'm=2 on restricted range; explained variance agrees with residuals.'],
            'open': ['Normal-tail recomputation does not reproduce the extreme printed '
                     'p-values literally. The m=3 and m=4 <DBL_MIN bounds exclude their '
                     'mathematical normal-tail values; naive 1-CDF subtraction yields zero.',
                     'The notes claim five of the first six p-values match to three significant '
                     'figures; only three do. Conditional significance decisions are unchanged.',
                     'Populated jackknife columns support that SEs were computed, but final '
                     'command logs/run scripts and raw block estimates remain unavailable.',
                     'A restricted fit or conditional edge p-value does not identify exactly '
                     'two historical migration events.'],
        },
        'new_package_availability_for_previously_missing_inputs': supplied_availability,
        'notes_treatment': 'Notes are hashed as an untrusted claim source. Claims about remote '
                           'identity, read-level observations, software internals and metadata '
                           'are not accepted as independently established by this checker.',
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--output', type=Path,
                        default=Path(__file__).resolve().parent / 'final_results_validation.json')
    args = parser.parse_args()
    report = audit(args.root.resolve())
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print(json.dumps({'output': str(args.output.resolve()),
                      'checks': report['check_summary'],
                      'bh_maximum_difference': report['baypass']['maximum_recomputed_q_difference'],
                      'first_six_tree_pvalues_matching_three_significant_figures':
                          report['treemix']['first_six_edges_matching_three_significant_figures'],
                      'final_null_calibration': 'unverifiable from supplied raw data'}))
    raise SystemExit(0 if all(check['passed'] for check in report['checks']) else 1)


if __name__ == '__main__':
    main()
