#!/usr/bin/env python3
"""Combine completed, hash-matched page inspections without inventing coverage."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

OUT = Path(__file__).resolve().parent


def identity(path):
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def main():
    if not __debug__:
        raise RuntimeError('Run without Python optimization; validation assertions must be enabled.')
    render_list = json.loads((OUT/'render_results.json').read_text())
    assert len(render_list) == 3
    assert {r['label'] for r in render_list} == {'article', 'manuscript', 'supplement'}
    renders = {r['label']: r for r in render_list}
    for label, ranges in [('manuscript', [(1, 100), (101, 150), (151, 197)]),
                          ('supplement', [(1, 100), (101, 198)])]:
        render = renders[label]
        assert identity(Path(render['source']['path'])) == render['source']
        assert identity(Path(render['rendered_pdf']['path'])) == render['rendered_pdf']
        assert len(render['page_images']) == render['pages']
        assert len({i['path'] for i in render['page_images']}) == render['pages']
        images = {int(Path(i['path']).stem.split('-')[-1]): i for i in render['page_images']}
        assert set(images) == set(range(1, render['pages']+1))
        approved = {}
        records = []
        observations = []
        for first, last in ranges:
            path = OUT/f'visual_{label}_part_{first}_{last}.json'
            part = json.loads(path.read_text())
            assert part['status'] == 'bounded_pass' and not part['findings'], path
            assert part['source'] == render['source'], path
            assert part['rendered_pdf'] == render['rendered_pdf'], path
            assert part['pages'] == render['pages'], path
            expected = list(range(first, last+1))
            assert sorted(part['original_detail_pages_inspected']) == expected, path
            assert len(part['page_images_inspected']) == len(expected), path
            part_images = {int(Path(i['path']).stem.split('-')[-1]): i
                           for i in part['page_images_inspected']}
            assert set(part_images) == set(expected), path
            assert not set(approved).intersection(part_images), path
            for page, item in part_images.items():
                assert item == images[page] == identity(Path(item['path'])), (path, page)
            approved.update(part_images)
            records.append({'record': identity(path), 'reviewer': part['reviewer'],
                            'original_detail_pages_inspected': expected})
            observations.extend(part.get('observations', []))
        expected_all = list(range(1, render['pages']+1))
        assert sorted(approved) == expected_all
        record = {'generated_utc': datetime.now(timezone.utc).isoformat(),
                  'label': label, 'source': render['source'], 'rendered_pdf': render['rendered_pdf'],
                  'pages': render['pages'], 'original_detail_pages_inspected': expected_all,
                  'page_images_inspected': [approved[n] for n in expected_all],
                  'part_reviews': records, 'findings': [], 'observations': observations,
                  'scope': 'Layout inspection of every final page at original image detail; '
                           'no certification of scientific claims or unresolved publication work.',
                  'status': 'bounded_pass'}
        (OUT/f'visual_{label}_review.json').write_text(json.dumps(record, indent=2)+'\n')
        print(json.dumps({'label': label, 'pages_inspected': len(approved), 'status': 'bounded_pass'}))


if __name__ == '__main__':
    main()
