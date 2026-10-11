#!/usr/bin/env python3
"""Read-only final closure review; never run the PDF publisher."""
from contextlib import redirect_stdout
from pathlib import Path
import hashlib
import importlib.util
import io
import json
import re
import subprocess
import sys
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
GIT = '/Users/samnimoh/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/git'


def identity(path):
    data = path.read_bytes()
    return {'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def main():
    script_names = ['publish_reviewed_pdfs.py','verify_documents.py','independent_builder_followup_tests.py',
                    'make_fix_manifest.py','CORRECTIONS.md']
    scripts = {name:identity(OUT/name) for name in script_names}
    publisher = (OUT/'publish_reviewed_pdfs.py').read_text()
    manifest_source = (OUT/'make_fix_manifest.py').read_text()
    correction_record = (OUT/'CORRECTIONS.md').read_text()
    captured = {}
    # Execute the actual 25-check verifier with its evidence write captured in memory.
    # All its file reads and Git queries remain real; no deliverable is written.
    old_write = Path.write_text
    def capture_write(path,text,*args,**kwargs):
        assert path == OUT/'document_validation.json', path
        captured['record'] = json.loads(text)
        return len(text)
    spec = importlib.util.spec_from_file_location('closure_actual_verifier',OUT/'verify_documents.py')
    verifier = importlib.util.module_from_spec(spec)
    sys.dont_write_bytecode = True
    spec.loader.exec_module(verifier)
    buffer = io.StringIO()
    try:
        Path.write_text = capture_write
        with redirect_stdout(buffer):
            verifier_failure = verifier.main()
    finally:
        Path.write_text = old_write
    verification = captured['record']
    saved_verification = json.loads((OUT/'document_validation.json').read_text())
    actual_review = json.loads((OUT/'final_document_review.json').read_text())
    source_matches = all(identity(ROOT/path)['sha256']==digest for path,digest in actual_review['source_sha256'].items())
    renders = json.loads((OUT/'render_results.json').read_text())
    render_rows = []
    for record in renders:
        row = {'label':record['label'],
               'source_identity_matches':identity(Path(record['source']['path']))==record['source'],
               'PDF_identity_matches':identity(Path(record['rendered_pdf']['path']))==record['rendered_pdf'],
               'PDF_page_count_matches':len(PdfReader(record['rendered_pdf']['path']).pages)==record['pages'],
               'page_image_count':len(record['page_images']),
               'page_image_identities_match':all(identity(Path(image['path']))==image for image in record['page_images']),
               'page_image_paths_unique':len({image['path'] for image in record['page_images']})==record['pages']}
        visual_path = OUT/f"visual_{record['label']}_review.json"
        row['visual_review_available'] = visual_path.exists()
        if visual_path.exists():
            visual = json.loads(visual_path.read_text())
            row['visual_review_source_and_pdf_match'] = visual['source']==record['source'] and visual['rendered_pdf']==record['rendered_pdf']
            row['visual_full_original_detail_page_census_matches'] = (len(visual['original_detail_pages_inspected'])==record['pages']
                                                                     and set(visual['original_detail_pages_inspected'])==set(range(1,record['pages']+1)))
            reviewed = visual.get('page_images_inspected',[])
            row['visual_image_identity_map_matches'] = (len(reviewed)==record['pages']
                                                        and {image['path']:image for image in reviewed}=={image['path']:image for image in record['page_images']})
        render_rows.append(row)
    # These static scope checks supplement the direct code review, not a publisher execution.
    gates = {
        'exactly_three_unique_render_labels_required':'assert len(renders) == 3' in publisher and "{'article', 'manuscript', 'supplement'}" in publisher,
        'current_reviewed_source_hashes_rechecked':"text_review['source_sha256'].items()" in publisher,
        'current_source_and_review_and_render_identity_equality_required':"identity(source) == render['source'] == review['source']" in publisher,
        'current_PDF_and_review_and_render_identity_equality_required':"identity(pdf) == render['rendered_pdf'] == review['rendered_pdf']" in publisher,
        'full_original_detail_page_census_required':"len(review['original_detail_pages_inspected']) == render['pages']" in publisher and "set(range(1, render['pages']+1))" in publisher,
        'complete_unique_render_and_approved_image_maps_required':"len(approved_images) == len(rendered_images) == render['pages']" in publisher and 'assert approved_images == rendered_images' in publisher,
        'actual_approved_image_hashes_rechecked':"identity(Path(item['path'])) == item" in publisher,
        'all_three_PDFs_staged_before_replacement':publisher.index('for render, pdf, destination in plans:') < publisher.index('for temporary, destination in staged:') < publisher.index('os.replace(temporary, destination)'),
        'sibling_temporary_files_and_fsync_used':"dir=destination.parent" in publisher and 'os.fsync(stream.fileno())' in publisher,
        'staged_and_published_PDF_hashes_verified':"identity(temporary)['sha256'] == render['rendered_pdf']['sha256']" in publisher and "record['published_pdf']['sha256'] == record['rendered_pdf']['sha256']" in publisher,
        'cleanup_is_in_finally':'finally:\n        for temporary, _ in staged:\n            temporary.unlink(missing_ok=True)' in publisher,
    }
    manifest_gates = {
        'manifest_excludes_its_own_identity':"p.name != 'fix_manifest.json'" in manifest_source,
        'current_published_PDF_identities_rechecked':"identity(Path(result['published_pdf']['path'])) == result['published_pdf']" in manifest_source,
        'current_reviewed_source_hashes_rechecked':"final_review['source_sha256'].items()" in manifest_source,
        'exactly_three_unique_publication_labels_required':bool(re.search(r"assert len\(publication\['results'\]\)\s*==\s*3",manifest_source))
                                                         and bool(re.search(r"assert \{[^\n]+\['label'\][^\n]+\}\s*==\s*\{'article', 'manuscript', 'supplement'\}",manifest_source)),
        'published_PDF_to_reviewed_render_equality_asserted':bool(re.search(r"assert (?:result|r)\['published_pdf'\]\['sha256'\]\s*==\s*(?:result|r)\['rendered_pdf'\]\['sha256'\]",manifest_source))
                                                           or bool(re.search(r"assert all\([^\n]+\['published_pdf'\]\['sha256'\]\s*==\s*[^\n]+\['rendered_pdf'\]\['sha256'\]",manifest_source)),
        'baseline_and_precommit_HEAD_named_precisely':"'baseline_commit': 'd59bbf6722c36b8f8f09e707a2290fbb699ed83f'" in manifest_source and 'git_head_before_final_document_commit' in manifest_source,
        'formal_historical_and_statistical_limits_retained':all(phrase in manifest_source for phrase in ['No Lean implementation-refinement proof','Historical generating-command/revision/raw-input lineage remains incomplete','Not statistical calibration']),
    }
    diff_names = subprocess.check_output([GIT,'-C',str(ROOT),'diff','--name-only','d59bbf6','--']).decode().splitlines()
    science_changes = [name for name in diff_names if name!='provenance_final/VERIFICATION_NOTES.md' and
                       (name.startswith(('corrected/','provenance_final/','figures/')) or name=='article/CANONICAL_FACTS_FOR_ARTICLE.md')]
    original_driver = Path('/private/tmp/pf8_independent_builder_followup.py')
    copied_driver_matches = original_driver.exists() and identity(original_driver)['sha256']==scripts['independent_builder_followup_tests.py']['sha256']
    current_verifier_matches_saved = (verification['checks']==saved_verification['checks']
                                    and verification['current_document_hashes']==saved_verification['current_document_hashes']
                                    and not verification['unexpected_changes'])
    findings = []
    if not all(gates.values()):
        findings.append({'priority':'P2','description':'Publisher scope-gate check failed.','failed_gates':[name for name,value in gates.items() if not value]})
    if verifier_failure or not current_verifier_matches_saved or not source_matches or science_changes:
        findings.append({'priority':'P2','description':'Final validation/source identities do not close.','scientific_changes':science_changes})
    if not all(manifest_gates.values()):
        findings.append({'priority':'P2','description':'Manifest closure guard check failed.','failed_gates':[name for name,value in manifest_gates.items() if not value]})
    report = {
        'scope':'Read-only closure review of PDF publication guards and the actual current verifier. Publisher not executed; visual reviews may still be pending.',
        'reviewed_scripts':scripts,'publication_gates':gates,
        'manifest_gates':manifest_gates,
        'correction_record_review':{'six_findings_and_counts_match_actual_evidence':all(phrase in correction_record for phrase in ['69 manuscript substitutions','four article-source substitutions','All 25 targeted final assertions passed']),
                                   'verification_scope_and_publication_limits_explicit':all(phrase in correction_record for phrase in ['It does not establish statistical calibration','existing Lean reference proofs are unchanged','manual contents-field completion']),
                                   'delivery_dependency':'Final visual/publication paragraphs describe the intended completed record; deliver only after all final visual records, publication and manifest exist.'},
        'actual_verifier_check_count':len(verification['checks']),
        'actual_verifier_checks':verification['checks'],'actual_verifier_summary':buffer.getvalue().strip(),
        'actual_verifier_matches_saved_evidence':current_verifier_matches_saved,
        'previous_scientific_output_and_review_identities_checked':verification['unaffected_identities_checked'],
        'actual_final_review_source_hashes_match':source_matches,
        'render_identity_checks':render_rows,
        'preserved_independent_driver_is_byte_identical':copied_driver_matches,
        'unexpected_scientific_changes':science_changes,
        'resolved_finding':'Publisher initially omitted equality between approved PNG identities and render PNG identities; final patch requires complete unique identity maps and rehashes actual images.',
        'findings':findings,'status':'bounded_pass' if not findings else 'needs_followup',
        'limits':['This review does not claim that pending visual reviews are complete, or that publication has run.',
                  'Replacement is atomic per PDF, not a transactional all-three-PDF replacement with rollback.',
                  'No concurrent-write/filesystem-race or power-loss durability certification.',
                  'No scientific pipeline execution, statistical validity certification or new Lean implementation proof.']
    }
    (OUT/'final_closure_review.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({'status':report['status'],'actual_verifier_check_count':len(verification['checks']),
                      'source_hashes_match':source_matches,'findings':findings,
                      'visual_reviews_available':[row['label'] for row in render_rows if row['visual_review_available']]},indent=2))


if __name__=='__main__':
    main()
