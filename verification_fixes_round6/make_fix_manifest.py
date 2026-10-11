#!/usr/bin/env python3
"""Record final correction evidence without claiming historical-run lineage."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import runpy

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
# Anchor shared helper discovery to this script so Python -I works from any cwd.
GIT = runpy.run_path(str(ROOT / 'tools' / 'git_runtime.py'))['resolve_git']()


def identity(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def main():
    if not __debug__:
        raise RuntimeError('Run without Python optimization; validation assertions must be enabled.')
    validation = json.loads((OUT/'document_validation.json').read_text())
    publication = json.loads((OUT/'pdf_publication_results.json').read_text())
    final_review = json.loads((OUT/'final_document_review.json').read_text())
    assert all(validation['checks'].values()) and publication['all_passed']
    assert len(publication['results']) == 3
    assert {r['label'] for r in publication['results']} == {'article', 'manuscript', 'supplement'}
    assert all(r['published_pdf']['sha256'] == r['rendered_pdf']['sha256'] for r in publication['results'])
    assert final_review['status'] == 'bounded_pass' and not final_review['findings']
    sources = [ROOT/p for p in ('Pf8_Ghana_manuscript_REVISED.docx', 'Pf8_Ghana_manuscript_REVISED.pdf',
        'article/Additional_file_1.docx', 'article/Additional_file_1.pdf', 'article/Pf8_Ghana_article.docx',
        'article/Pf8_Ghana_article.pdf', 'article/article.md', 'article/CANONICAL_FACTS_FOR_ARTICLE.md',
        'tools/apply_edits.py', 'tools/build_article.py', 'tools/make_supplement.py',
        'tools/references_apa.txt', 'tools/README.md', 'provenance_final/VERIFICATION_NOTES.md')]
    visual = []
    for result in publication['results']:
        label = result['label']
        review = json.loads((OUT/f'visual_{label}_review.json').read_text())
        assert identity(Path(result['source']['path'])) == result['source']
        assert identity(Path(result['published_pdf']['path'])) == result['published_pdf']
        assert review['source'] == result['source'] and review['rendered_pdf'] == result['rendered_pdf']
        assert review['status'] == 'bounded_pass' and not review['findings']
        visual.append({'label': label, 'pages': review['pages'],
                       'original_detail_pages_inspected': review['original_detail_pages_inspected'],
                       'review_sha256': identity(OUT/f'visual_{label}_review.json')['sha256']})
    for relative, digest in final_review['source_sha256'].items():
        assert identity(ROOT/relative)['sha256'] == digest, relative
    record = {'generated_utc': datetime.now(timezone.utc).isoformat(),
        'objective': 'Address six round-six editorial/tooling findings and synchronize reviewed documents.',
        'baseline_commit': 'd59bbf6722c36b8f8f09e707a2290fbb699ed83f',
        'git_head_before_final_document_commit': subprocess.check_output([GIT, 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'source_and_deliverable_identities': [identity(p) for p in sources],
        'editorial_substitutions': {'manuscript': 69, 'article_source': 4},
        'intended_formatting': 'Only declared heading pagination flags and repeated article table headers.',
        'scientific_numerical_tokens_preserved': validation['checks']['scientific_numerical_tokens_preserved'],
        'unaffected_identities_checked': validation['unaffected_identities_checked'],
        'unexpected_changes': validation['unexpected_changes'],
        'targeted_assertions': {'passed': sum(validation['checks'].values()), 'total': len(validation['checks'])},
        'helper_test_counts': {'primary_editor': 49, 'primary_builder': 38, 'independent_editor': 14,
                               'independent_builder': 30, 'independent_builder_layout_package_failures': 15},
        'visual_review_coverage': visual,
        'published_PDFs_match_reviewed_renders': all(r['published_pdf']['sha256'] == r['rendered_pdf']['sha256'] for r in publication['results']),
        'evidence_identities': [identity(p) for p in sorted(OUT.iterdir()) if p.is_file() and p.name != 'fix_manifest.json'],
        'scope_limits': ['No new scientific calculation or biological audit execution.',
                         'No Lean implementation-refinement proof added; existing reference proofs unchanged.',
                         'Historical generating-command/revision/raw-input lineage remains incomplete.',
                         'Not statistical calibration, full OOXML schema or image-decoding certification.',
                         'Publication placeholders and contents-field completion remain separate work.'],
        'status': 'six_scoped_findings_addressed'}
    (OUT/'fix_manifest.json').write_text(json.dumps(record, indent=2)+'\n')
    print(json.dumps({'status': record['status'], 'assertions': record['targeted_assertions'],
                      'pages': {v['label']: v['pages'] for v in visual}}))


if __name__ == '__main__':
    main()
