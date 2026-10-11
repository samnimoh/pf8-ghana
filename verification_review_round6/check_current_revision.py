#!/usr/bin/env python3
"""Check reported fixes and remaining findings without executing scientific code."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import runpy
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
# Anchor shared helper discovery to this script so Python -I works from any cwd.
GIT = runpy.run_path(str(ROOT / 'tools' / 'git_runtime.py'))['resolve_git']()
HEAD = 'd59bbf6722c36b8f8f09e707a2290fbb699ed83f'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def identity(p):
    data = p.read_bytes()
    return {'path': str(p), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def document(p):
    with zipfile.ZipFile(p) as z:
        paragraphs = [''.join(n.text or '' for n in q.iter(W + 't'))
                      for q in ET.fromstring(z.read('word/document.xml')).iter(W + 'p')]
        xml_sha = hashlib.sha256(z.read('word/document.xml')).hexdigest()
    return '\n'.join(paragraphs), paragraphs, xml_sha


def main():
    paths = {'main': ROOT / 'Pf8_Ghana_manuscript_REVISED.docx',
             'supplement': ROOT / 'article/Additional_file_1.docx',
             'article': ROOT / 'article/Pf8_Ghana_article.docx',
             'notes': ROOT / 'provenance_final/VERIFICATION_NOTES.md',
             'references': ROOT / 'tools/references_apa.txt',
             'lean_validation': ROOT / 'verification_audit/lean_validation.json'}
    inputs = {key: identity(p) for key, p in paths.items()}
    docs = {key: document(paths[key]) for key in ('main', 'supplement', 'article')}
    inventory = json.loads((OUT / 'change_inventory.json').read_text())
    tools = json.loads((OUT / 'independent_tool_review.json').read_text())
    tests = {r['name']: r for r in tools['results']}
    render = json.loads((OUT / 'render_review.json').read_text())
    checks = {}
    for key in ('main', 'supplement'):
        text, pars, _ = docs[key]
        checks[key + '_calibration_caveat_propagated'] = ('proper matching lowered the threshold' in text and
            'does not establish the direction of the error for the final 3,916-SNP run' in text)
        checks[key + '_reviewed_fdr_summary_is_conditional'] = ('control being conditional on that null being adequately calibrated' in text)
        checks[key + '_named_statistic_correction_present'] = ('Stability of a very low, detectable common-variant estimate is not an estimate of random mating' in text)
        checks[key + '_named_treemix_correction_present'] = ('within this fitted covariance model' in text and 'does not propagate error in the graph structure itself' in text)
        checks[key + '_live_panmixia_claims_remain'] = ('Near-panmixia is now supported by FST stability' in text and
            'the panmixia estimate was always well determined' in text and
            'made near-panmixia the best-evidenced conclusion in the manuscript' in text)
        checks[key + '_broader_treemix_conclusions_remain'] = ('A strictly bifurcating population tree is inadequate' in text and
            'High that a bifurcating tree is inadequate' in text)
        captions = [p for p in pars if re.match(r'^(Table|Figure)\s+\S+\.', p)]
        checks[key + '_two_truncated_captions_remain'] = sum('This table is new in this revision and is.' in p for p in captions) == 2
        obsolete = ('numbered after', 'lettered to preserve', 'preserves the numbering', 'preserve the numbering', 'later numbers')
        checks[key + '_obsolete_caption_numbering_clauses_removed'] = not any(q in p for p in captions for q in obsolete)
    _, suppars, _ = docs['supplement']
    labels = {kind: [m[1] for p in suppars if (m := re.match(rf'^{kind}\s+(S\d+)\.', p))] for kind in ('Table', 'Figure')}
    checks['supplement_unique_contiguous_labels'] = all(vals == [f'S{i}' for i in range(1, count + 1)]
        for vals, count in ((labels['Table'], 52), (labels['Figure'], 23)))
    cascade = next(p for p in suppars if 'The cascade, defined once' in p)
    s29 = next(p for p in suppars if p.startswith('Table S29.'))
    checks['supplement_cascade_points_to_unrelated_admixture_table'] = 'Table S29' in cascade and 'cross-validation' in s29 and 'ADMIXTURE' in s29
    notes = paths['notes'].read_text()
    checks['superseded_notes_banner_present'] = 'Superseded in part' in notes and 'twelve of fifteen' in notes
    checks['notes_called_field_qualification_present'] = 'consistent with a real variant in the release’s called fields' in notes
    checks['vendored_reference_list_has_42_entries'] = len([p for p in paths['references'].read_text().splitlines() if p.strip()]) == 42
    checks['vendored_reference_identity_retains_prior_list'] = inputs['references']['sha256'] == '7c9333469481e1c4f2ac1fd665ec1c8db0dc115fcc002a509d2d1cdf0c409738'
    checks['helper_sources_unchanged_during_independent_tests'] = tools['source_hashes_before'] == tools['source_hashes_after'] == {
        p: identity(Path(p))['sha256'] for p in tools['source_hashes_before']}
    checks['optional_editor_metadata_supported'] = tests['optional_metadata']['returncode'] == 0
    checks['unmatched_edit_rejected_without_write'] = tests['unmatched_no_write']['returncode'] != 0 and tests['unmatched_no_write']['document_unchanged']
    checks['exact_duplicate_quote_rejected_without_write'] = tests['exact_duplicates_rejected']['returncode'] != 0 and tests['exact_duplicates_rejected']['document_unchanged']
    checks['exact_second_occurrence_edits_second_quote'] = tests['exact_occurrence2']['result_paragraphs'] == ['alpha beta', 'new phrase']
    checks['whitespace_ambiguity_is_still_silently_accepted'] = tests['whitespace_duplicates']['returncode'] == 0 and tests['whitespace_duplicates']['result_paragraphs'] == ['new phrase', 'alpha   beta']
    checks['whitespace_second_occurrence_still_edits_first'] = tests['whitespace_occurrence2']['result_paragraphs'] == ['new phrase', 'alpha   beta']
    checks['out_of_range_occurrence_still_accepted_for_unique_match'] = tests['unique_bad_occurrence']['returncode'] == 0 and not tests['unique_bad_occurrence']['document_unchanged']
    checks['cross_paragraph_quote_still_edits_distinct_blocks'] = tests['cross_paragraph_quote']['result_paragraphs'] == ['end of merged', ' of next']
    checks['article_build_from_unrelated_directory_matches_current_xml'] = tests['normal_build_from_unrelated_directory']['exact_current_document_xml_match'] and tests['normal_build_from_unrelated_directory']['generated_document_xml_sha256'] == docs['article'][2]
    checks['supplement_build_matches_current_xml'] = tests['normal_supplement_from_copied_manuscript_xml']['exact_xml_match'] and tests['normal_supplement_from_copied_manuscript_xml']['generated_xml_sha256'] == docs['supplement'][2]
    for phase in ('archive_write', 'integrity_check', 'fsync', 'replace'):
        result = tests['builder_failure_' + phase]
        checks['atomic_builder_preserves_destination_on_' + phase] = result['returncode'] != 0 and result['destination_preserved'] and not result['temporary_archive_exists']
    missing = tests['required_figure_missing']
    checks['missing_figure_still_replaces_valid_destination'] = missing['returncode'] == 0 and not missing['destination_preserved'] and missing['zip_crc_error'] is None and bool(missing['unresolved_document_relationships'])
    checks['all_413_pdf_page_texts_match_fresh_conversions'] = sum(r['fresh_pages'] for r in render['comparisons']) == 413 and all(r['all_page_texts_match'] for r in render['comparisons'])
    server_map = {'dimred_comparison.csv': 'corrected/dimred_comparison_n4905_qcpassset.csv',
                  'dimred_comparison_qcset.csv': 'corrected/dimred_comparison_n1900_analysisset.csv',
                  'fst_pairwise.csv': 'corrected/final_fst_pairwise.csv',
                  'sensitivity_summary.csv': 'corrected/sensitivity_summary.csv',
                  'mantel_jackknife_region.csv': 'corrected/mantel_jackknife_region.csv'}
    remote = []
    for line in (OUT / 'server_checksums.txt').read_text().splitlines():
        expected, server_path = line.split(maxsplit=1)
        local = ROOT / server_map[Path(server_path).name]
        observed = hashlib.md5(local.read_bytes()).hexdigest()
        remote.append({'server_path': server_path, 'server_md5': expected, 'local': identity(local), 'local_md5': observed, 'matches': observed == expected})
    checks['five_saved_server_outputs_match_current_local_copies'] = len(remote) == 5 and all(r['matches'] for r in remote)
    changed = {r['path'] for r in inventory['changed_files']}
    unchanged_targets = ['article/article.md', 'article/Pf8_Ghana_article.docx', 'article/CANONICAL_FACTS_FOR_ARTICLE.md',
        'corrected/dimred_comparison_n1900_analysisset.csv', 'corrected/dimred_comparison_n4905_qcpassset.csv',
        'corrected/dimred_comparison_zone_qcset.png', 'verification_audit/lean_validation.json']
    known = {r['path'] for r in inventory['files']}
    checks['article_numeric_sources_figure_and_lean_record_unchanged_since_round5'] = all(str(ROOT / p) in known and str(ROOT / p) not in changed for p in unchanged_targets)
    lean = json.loads(paths['lean_validation'].read_text())
    checks['existing_lean_record_has_16_reference_axiom_reports'] = lean['axiom_report_count'] == 16
    head = subprocess.check_output([GIT, 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    checks['reviewed_git_head_unchanged'] = head == HEAD
    record = {'generated_utc': datetime.now(timezone.utc).isoformat(), 'git_reviewed_head': head,
        'assertion_meaning': 'Passing confirms the stated fix or reproduces a stated remaining finding. It is not statistical, formal implementation, or complete provenance certification.',
        'input_identities': inputs, 'assertions': checks, 'server_output_checks': remote,
        'helper_test_count': len(tests), 'supplement_labels': labels,
        'limits': ['No scientific pipeline or biological audit script was run.',
                   'Document helper executions used scratch copies or synthetic inputs.',
                   'No new Lean build or implementation-refinement proof was performed.']}
    (OUT / 'revision_validation.json').write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    failed = [key for key, passed in checks.items() if not passed]
    print(json.dumps({'passed': sum(checks.values()), 'total': len(checks), 'failed': failed}))
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
