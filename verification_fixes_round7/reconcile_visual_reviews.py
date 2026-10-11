#!/usr/bin/env python3
"""Carry forward inspected identical pixels and require fresh changed-page QA."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent
INITIAL = OUT / 'initial_visual_reviews'
RECORDS = {
    'article': [('visual_article_review.json', 1, 18, '/root')],
    'manuscript': [('visual_manuscript_part_1_100.json', 1, 100, '/root/final_document_check'),
                   ('visual_manuscript_part_101_150.json', 101, 150, '/root/fix_builder'),
                   ('visual_manuscript_part_151_197.json', 151, 197, '/root/fix_editor')],
    'supplement': [('visual_supplement_part_1_100.json', 1, 100, '/root/fix_builder'),
                   ('visual_supplement_part_101_198.json', 101, 198, '/root/fix_editor')],
}


def identity(path):
    path = Path(path)
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def read(path):
    return json.loads(path.read_text())


def indexed_images(items):
    result = {}
    for item in items:
        page = int(Path(item['path']).stem.split('-')[-1])
        assert page not in result
        result[page] = item
    return result


def render_map(path):
    rows = read(path)
    assert len(rows) == 3 and {r['label'] for r in rows} == set(RECORDS)
    return {r['label']: r for r in rows}


def main():
    if not __debug__:
        raise RuntimeError('Validation assertions must remain enabled.')
    old = render_map(INITIAL / 'render_results.json')
    new = render_map(OUT / 'render_results.json')
    snapshot = read(INITIAL / 'snapshot_locations.json')
    backups = {i['original']: i for i in snapshot['page_images']}
    assert len(backups) == len(snapshot['page_images']) == 413
    backup_root = Path(snapshot['png_backup'])
    plans, results = [], []
    for label, parts in RECORDS.items():
        previous, current = old[label], new[label]
        assert previous['pages'] == current['pages']
        assert current['source'] == identity(current['source']['path'])
        assert current['rendered_pdf'] == identity(current['rendered_pdf']['path'])
        old_pdf = Path(previous['rendered_pdf']['path'])
        saved_pdf = identity(backup_root / label / old_pdf.name)
        assert saved_pdf['sha256'] == previous['rendered_pdf']['sha256']
        assert saved_pdf['bytes'] == previous['rendered_pdf']['bytes']
        old_images = indexed_images(previous['page_images'])
        new_images = indexed_images(current['page_images'])
        expected_all = set(range(1, current['pages'] + 1))
        assert set(old_images) == set(new_images) == expected_all
        changed = set()
        backup_proofs = {}
        for page in sorted(expected_all):
            initial, final = old_images[page], new_images[page]
            assert initial['path'] == final['path']
            backup = backups[initial['path']]
            saved = identity(backup['backup'])
            assert saved['sha256'] == backup['sha256'] == initial['sha256']
            assert saved['bytes'] == initial['bytes']
            assert final == identity(final['path'])
            if initial['sha256'] != final['sha256']:
                changed.add(page)
            backup_proofs[page] = saved
        followup_path = OUT / f'visual_{label}_followup_pages.json'
        followup = read(followup_path) if followup_path.exists() else None
        if changed:
            assert followup is not None and followup['label'] == label
            assert followup['status'] == 'bounded_pass' and not followup['findings']
            assert followup['source'] == current['source']
            assert followup['rendered_pdf'] == current['rendered_pdf']
            assert followup['pages'] == current['pages']
            assert sorted(followup['original_detail_pages_inspected']) == sorted(changed)
            assert indexed_images(followup['page_images_inspected']) == {n: new_images[n] for n in changed}
        elif followup:
            raise AssertionError('Unexpected followup record for unchanged pixels')
        covered = set()
        for filename, first, last, reviewer in parts:
            initial_path = INITIAL / filename
            initial = read(initial_path)
            pages = list(range(first, last + 1))
            assert not covered.intersection(pages)
            covered.update(pages)
            assert initial['label'] == label and initial['status'] == 'bounded_pass' and not initial['findings']
            assert initial['source'] == previous['source'] and initial['rendered_pdf'] == previous['rendered_pdf']
            assert initial['pages'] == current['pages']
            assert sorted(initial['original_detail_pages_inspected']) == pages
            assert indexed_images(initial['page_images_inspected']) == {n: old_images[n] for n in pages}
            assert initial.get('reviewer', reviewer).lstrip('/') == reviewer.lstrip('/')
            fresh = sorted(changed.intersection(pages))
            retained = sorted(set(pages) - changed)
            record = {
                'generated_utc': datetime.now(timezone.utc).isoformat(),
                'label': label, 'reviewer': reviewer, 'status': 'bounded_pass',
                'source': current['source'], 'rendered_pdf': current['rendered_pdf'],
                'pages': current['pages'], 'original_detail_pages_inspected': pages,
                'page_images_inspected': [new_images[n] for n in pages],
                'findings': [], 'observations': initial.get('observations', []),
                'scope': 'Final layout coverage consists of previously opened original-detail '
                         'PNG pixels retained only after exact byte identity checks, plus fresh '
                         'original-detail inspections of every changed page. This does not claim '
                         'that unchanged final pathnames were opened again or certify science.',
                'limitations': initial.get('limitations', []),
                'reconciliation': {
                    'initial_review': identity(initial_path),
                    'initial_render_manifest': identity(INITIAL / 'render_results.json'),
                    'snapshot_manifest': identity(INITIAL / 'snapshot_locations.json'),
                    'initial_source': previous['source'], 'initial_rendered_pdf_backup': saved_pdf,
                    'retained_identical_pages': retained, 'freshly_inspected_pages': fresh,
                    'fresh_review': identity(followup_path) if fresh else None,
                    'fresh_reviewer': followup['reviewer'] if fresh else None,
                    'preserved_initial_pngs': [backup_proofs[n] for n in pages],
                },
            }
            plans.append((OUT / filename, record))
        assert covered == expected_all
        results.append({'label': label, 'pages': current['pages'],
                        'retained_identical_pages': sorted(expected_all - changed),
                        'freshly_inspected_pages': sorted(changed)})
    # Check the entire chain before writing any replacement review record.
    for path, record in plans:
        path.write_text(json.dumps(record, indent=2) + '\n')
    report = {'generated_utc': datetime.now(timezone.utc).isoformat(),
              'status': 'bounded_pass', 'results': results,
              'total_pages': sum(r['pages'] for r in results),
              'retained_identical_page_count': sum(len(r['retained_identical_pages']) for r in results),
              'freshly_inspected_page_count': sum(len(r['freshly_inspected_pages']) for r in results),
              'scope': 'Actual initial inspection evidence preserved; final changed pixels freshly inspected.'}
    (OUT / 'visual_reconciliation_results.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ['status', 'total_pages', 'retained_identical_page_count', 'freshly_inspected_page_count']}))


if __name__ == '__main__':
    main()
