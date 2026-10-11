"""Bind final local deliverables to completed bounded review evidence."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import runpy
import subprocess

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent


def identity(path):
    path = Path(path)
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def read(name):
    return json.loads((OUT / name).read_text())


def main():
    if not __debug__:
        raise RuntimeError('Validation assertions must remain enabled.')
    review = read('final_document_followup_review.json')
    validation = read('document_validation.json')
    publication = read('pdf_publication_results.json')
    reconciliation = read('visual_reconciliation_results.json')
    assert review['status'] == validation['status'] == reconciliation['status'] == 'bounded_pass'
    assert not review['findings'] and all(c['pass'] for c in review['checks'])
    assert all(validation['checks'].values()) and publication['all_passed']
    assert reconciliation['total_pages'] == 413
    assert reconciliation['retained_identical_page_count'] == 405
    assert reconciliation['freshly_inspected_page_count'] == 8
    assert all(identity(ROOT / name)['sha256'] == digest for name, digest in review['source_sha256'].items())
    packages = []
    for item in publication['results']:
        label = item['label']
        visual = read(f'visual_{label}_review.json')
        assert visual['status'] == 'bounded_pass' and not visual['findings']
        assert identity(item['source']['path']) == item['source'] == visual['source']
        assert identity(item['published_pdf']['path']) == item['published_pdf']
        assert item['published_pdf']['sha256'] == item['rendered_pdf']['sha256'] == visual['rendered_pdf']['sha256']
        assert sorted(visual['original_detail_pages_inspected']) == list(range(1, item['pages'] + 1))
        packages.append({'label': label, 'docx': item['source'], 'pdf': item['published_pdf'], 'pages': item['pages']})
    assert len(packages) == 3 and {p['label'] for p in packages} == {'article', 'manuscript', 'supplement'}
    reports = [
        'final_document_followup_review.json', 'document_validation.json',
        'visual_reconciliation_results.json', 'pdf_publication_results.json',
        'independent_visual_reconciliation_review.json', 'independent_final_protection_review.json',
        'independent_publication_gate_review.json', 'independent_visual_merge_adapter_review.json',
        'independent_publisher_adapter_review.json', 'git_portability_results.json',
        'independent_git_probe_results.json', 'independent_git_review.json',
        'builder_regression_results.json', 'builder_round6_regression_results.json',
        'builder_encoded_core_followup_results.json', 'independent_builder_followup_results.json',
        'independent_builder_followup_review.json', 'builder_equivalence_followup_results.json',
        'independent_followup_document_driver_review_final.json',
        'visual_article_review.json', 'visual_manuscript_review.json', 'visual_supplement_review.json',
    ]
    for name in ['independent_visual_reconciliation_review.json', 'independent_final_protection_review.json']:
        independent = read(name)
        assert independent['status'] == 'bounded_pass' and not independent['findings']
    protection = read('independent_final_protection_review.json')
    assert protection['bound_sources'] == review['source_sha256']
    assert protection['validation_record'] == identity(OUT / 'document_validation.json')
    assert all(item == identity(item['path']) for item in protection['reviewed_scripts'])
    visual_chain = read('independent_visual_reconciliation_review.json')
    assert visual_chain['reviewed_script'] == identity(OUT / 'reconcile_visual_reviews.py')
    assert visual_chain['reviewed_reconciliation_report'] == identity(OUT / 'visual_reconciliation_results.json')
    assert all(item == identity(item['path']) for item in visual_chain['reviewed_manifests'].values())
    assert all(pair[k] == identity(pair[k]['path']) for pair in visual_chain['reviewed_records'] for k in ['initial', 'final'])
    assert all(item == identity(item['path']) for item in visual_chain['reviewed_followup_records'])
    current_builder = identity(ROOT / 'tools/build_article.py')
    encoded = read('builder_encoded_core_followup_results.json')
    independent_builder = read('independent_builder_followup_results.json')
    assert encoded['builder'] == independent_builder['builder'] == current_builder
    assert encoded['all_passed'] and independent_builder['all_passed']
    assert len(encoded['results']) == encoded['checks'] == 8 and all(c['passed'] for c in encoded['results'])
    assert len(independent_builder['tests']) == independent_builder['tests_passed'] == 12 and all(c['passed'] for c in independent_builder['tests'])
    original_cases = read('builder_regression_results.json')
    inherited_cases = read('builder_round6_regression_results.json')
    assert original_cases['all_passed'] and inherited_cases['all_passed']
    assert len(original_cases['tests']) == original_cases['tests_passed'] == 21 and all(c['passed'] for c in original_cases['tests'])
    assert len(inherited_cases['results']) == 38 and all(c['passed'] for c in inherited_cases['results'])
    assert original_cases['builder']['sha256'] == inherited_cases['builder_sha256_before'] == inherited_cases['builder_sha256_after'] == '55a7b960ab42804d814e783d660b8573985d17fd0330abeac5b650311ed2ef2f'
    equivalent = read('builder_equivalence_followup_results.json')
    assert equivalent['all_passed'] and equivalent['all_uncompressed_package_parts_identical']
    assert equivalent['builder_sha256'] == current_builder['sha256']
    assert equivalent['current_article_sha256'] == identity(ROOT / 'article/Pf8_Ghana_article.docx')['sha256']
    fixes = [
        ('correction_record', 'Table F.2/S52 matches the narrower detectable common-variant conclusion.'),
        ('all_23_codons_fixed', 'Twenty-two fixed codons plus the codon458 exception in the named cell and three equivalent passages.'),
        ('table_8_1_negligible_status', 'Table 8.1/S42 now says very low but detectable retained common-variant differentiation.'),
        ('near_panmixia_10_1', 'The historically attributed label now carries an explicit local withdrawal cue.'),
        ('temporary_symlink', 'Assembler uses an exclusive owned descriptor and validates before replacing the destination.'),
        ('metadata_title', 'Generated article and supplement core titles match their visible titles.'),
        ('nine_git_literals', 'Nine review utilities use validated PF8_GIT or PATH resolution and script-relative imports.'),
        ('table_order', 'Article first citations and physical tables follow1,2,3,4.'),
        ('duplicate_n_headers', 'Table2 labels the two count columns as first zone and second zone.'),
    ]
    git = runpy.run_path(str(ROOT / 'tools/git_runtime.py'))['resolve_git']()
    manifest = {
        'generated_utc': datetime.now(timezone.utc).isoformat(), 'status': 'bounded_pass',
        'baseline_commit': 'e7c4cd41b1f631209d25f2ff35eed6ba9c0ec6cd',
        'pre_final_commit': subprocess.check_output([git, '-C', str(ROOT), 'rev-parse', 'HEAD'], text=True).strip(),
        'addressed_findings': [{'id': i, 'status': 'addressed', 'change': text} for i, text in fixes],
        'deliverables': packages, 'evidence': [identity(OUT / name) for name in reports],
        'canonical_facts': identity(ROOT / 'article/CANONICAL_FACTS_FOR_ARTICLE.md'),
        'verification_notes': identity(ROOT / 'provenance_final/VERIFICATION_NOTES.md'),
        'tools': [identity(ROOT / p) for p in ['tools/build_article.py', 'tools/make_supplement.py', 'tools/git_runtime.py']],
        'final_review_counts': {'document_checks': len(review['checks']), 'package_protection_checks': len(validation['checks']),
                                'pages_covered': 413, 'identical_prior_inspected_pixels': 405, 'fresh_changed_page_inspections': 8},
        'test_revision_note': 'The59 original assembler cases bind revision55a7b960. The subsequent single normalization-line change binds revision9d90d195 through eight targeted checks,12 independent cases and actual package-part equivalence. Earlier failed/limited evidence remains historical.',
        'scope': 'Confirmed editorial, metadata, table presentation and local tool corrections. No biological analysis, data/result regeneration, server execution or Python-to-Lean refinement proof.',
        'limitations': ['Preserved inherited minor figure/table caption page breaks and unfilled publication placeholders.',
                        'Historical numerical/provenance claims are not newly certified by these document and tool checks.',
                        'Each PDF replacement is atomic; the three replacements are not a single filesystem transaction.'],
    }
    (OUT / 'fix_manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    print(json.dumps({'status': manifest['status'], 'findings_addressed': len(fixes), 'documents': len(packages), 'pages': 413}))


if __name__ == '__main__':
    main()
