#!/usr/bin/env python3
"""Independent read-only chain audit and harmless scratch reconciliation probes."""
from contextlib import redirect_stdout
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parent
SCRIPT = ROOT / 'reconcile_visual_reviews.py'
PARTS = {
    'article': [('visual_article_review.json', 1, 18, '/root')],
    'manuscript': [('visual_manuscript_part_1_100.json', 1, 100, '/root/final_document_check'),
                   ('visual_manuscript_part_101_150.json', 101, 150, '/root/fix_builder'),
                   ('visual_manuscript_part_151_197.json', 151, 197, '/root/fix_editor')],
    'supplement': [('visual_supplement_part_1_100.json', 1, 100, '/root/fix_builder'),
                   ('visual_supplement_part_101_198.json', 101, 198, '/root/fix_editor')],
}
FRESH = {'article': [], 'manuscript': [83, 88, 127, 128],
         'supplement': [84, 89, 128, 129]}


def identity(path):
    path = Path(path)
    data = path.read_bytes()
    return {'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def read(path):
    return json.loads(Path(path).read_text())


def write(path, data):
    Path(path).write_text(json.dumps(data, indent=2) + '\n')


def index(items, count):
    assert len(items) == count
    rows = {}
    for item in items:
        page = int(Path(item['path']).stem.removeprefix('page-'))
        assert page not in rows
        rows[page] = item
    return rows


def actual_audit():
    old_path = ROOT / 'initial_visual_reviews/render_results.json'
    new_path = ROOT / 'render_results.json'
    snapshot_path = ROOT / 'initial_visual_reviews/snapshot_locations.json'
    old_list, new_list = read(old_path), read(new_path)
    assert len(old_list) == len(new_list) == 3
    assert {r['label'] for r in old_list} == {r['label'] for r in new_list} == set(PARTS)
    old, new = ({r['label']: r for r in rows} for rows in (old_list, new_list))
    snapshot = read(snapshot_path)
    assert len(snapshot['page_images']) == 413
    backups = {r['original']: r for r in snapshot['page_images']}
    assert len(backups) == 413
    results, records = [], []
    for label, parts in PARTS.items():
        previous, current = old[label], new[label]
        count = {'article': 18, 'manuscript': 197, 'supplement': 198}[label]
        assert previous['pages'] == current['pages'] == count
        assert identity(current['source']['path']) == current['source']
        assert identity(current['rendered_pdf']['path']) == current['rendered_pdf']
        saved_pdf = identity(Path(snapshot['png_backup']) / label / Path(previous['rendered_pdf']['path']).name)
        assert saved_pdf['bytes'] == previous['rendered_pdf']['bytes']
        assert saved_pdf['sha256'] == previous['rendered_pdf']['sha256']
        old_images, new_images = index(previous['page_images'], count), index(current['page_images'], count)
        assert set(old_images) == set(new_images) == set(range(1, count + 1))
        changed, preserved = [], {}
        for page in range(1, count + 1):
            old_image, new_image = old_images[page], new_images[page]
            assert old_image['path'] == new_image['path']
            saved = backups[old_image['path']]
            actual_saved = identity(saved['backup'])
            assert actual_saved['bytes'] == old_image['bytes']
            assert actual_saved['sha256'] == old_image['sha256'] == saved['sha256']
            assert identity(new_image['path']) == new_image
            # Independently compare bytes, not only equality of declared hashes.
            if Path(saved['backup']).read_bytes() != Path(new_image['path']).read_bytes():
                changed.append(page)
            preserved[page] = actual_saved
        assert changed == FRESH[label]
        followup_path = ROOT / f'visual_{label}_followup_pages.json'
        followup = read(followup_path) if changed else None
        if changed:
            assert followup['label'] == label and followup['status'] == 'bounded_pass'
            assert followup['findings'] == []
            assert followup['source'] == current['source']
            assert followup['rendered_pdf'] == current['rendered_pdf'] and followup['pages'] == count
            assert sorted(followup['original_detail_pages_inspected']) == changed
            assert index(followup['page_images_inspected'], len(changed)) == {p: new_images[p] for p in changed}
            assert followup['reviewer'] == {'manuscript': '/root', 'supplement': '/root/fix_editor'}[label]
        else:
            assert not followup_path.exists()
        covered = []
        for name, first, last, reviewer in parts:
            initial_path, final_path = ROOT / 'initial_visual_reviews' / name, ROOT / name
            initial, final = read(initial_path), read(final_path)
            pages = list(range(first, last + 1))
            covered.extend(pages)
            assert initial['label'] == final['label'] == label
            assert initial['status'] == final['status'] == 'bounded_pass'
            assert initial['findings'] == final['findings'] == []
            assert initial['source'] == previous['source'] and initial['rendered_pdf'] == previous['rendered_pdf']
            assert final['source'] == current['source'] and final['rendered_pdf'] == current['rendered_pdf']
            assert initial['pages'] == final['pages'] == count
            assert sorted(initial['original_detail_pages_inspected']) == final['original_detail_pages_inspected'] == pages
            assert index(initial['page_images_inspected'], len(pages)) == {p: old_images[p] for p in pages}
            assert index(final['page_images_inspected'], len(pages)) == {p: new_images[p] for p in pages}
            assert initial.get('reviewer', reviewer).lstrip('/') == reviewer.lstrip('/')
            assert final['reviewer'] == reviewer
            assert final['observations'] == initial.get('observations', [])
            assert final['limitations'] == initial.get('limitations', [])
            rec = final['reconciliation']
            fresh = sorted(set(pages).intersection(changed))
            retained = sorted(set(pages).difference(changed))
            assert rec['initial_review'] == identity(initial_path)
            assert rec['initial_render_manifest'] == identity(old_path)
            assert rec['snapshot_manifest'] == identity(snapshot_path)
            assert rec['initial_source'] == previous['source']
            assert rec['initial_rendered_pdf_backup'] == saved_pdf
            assert rec['retained_identical_pages'] == retained
            assert rec['freshly_inspected_pages'] == fresh
            assert rec['fresh_review'] == (identity(followup_path) if fresh else None)
            assert rec['fresh_reviewer'] == (followup['reviewer'] if fresh else None)
            assert rec['preserved_initial_pngs'] == [preserved[p] for p in pages]
            records.append({'initial': identity(initial_path), 'final': identity(final_path)})
        assert covered == list(range(1, count + 1))
        results.append({'label': label, 'pages': count,
                        'retained_identical_pages': sorted(set(range(1, count + 1)).difference(changed)),
                        'freshly_inspected_pages': changed})
    report = read(ROOT / 'visual_reconciliation_results.json')
    assert report['status'] == 'bounded_pass' and report['results'] == results
    assert report['total_pages'] == 413
    assert report['retained_identical_page_count'] == 405
    assert report['freshly_inspected_page_count'] == 8
    # These are our two immutable original records, witnessed before reconciliation.
    assert identity(ROOT / 'initial_visual_reviews/visual_manuscript_part_101_150.json')['sha256'] == '08dd2a7fc9abd699800fba85cec5bcd0451a514ddb5afbb3f0779f8f613bd3b3'
    assert identity(ROOT / 'initial_visual_reviews/visual_supplement_part_1_100.json')['sha256'] == '61483b19a205d6622c610b03a228a5239b3031dfeebcdce8e04c399b8efee17a'
    return {'status': 'pass', 'pages': 413, 'direct_byte_identical_pages': 405,
            'changed_pages': FRESH, 'review_records': records,
            'followup_records': [identity(ROOT / f'visual_{label}_followup_pages.json') for label in ('manuscript', 'supplement')],
            'initial_render_manifest': identity(old_path), 'final_render_manifest': identity(new_path),
            'snapshot_manifest': identity(snapshot_path)}


def make_fixture(base):
    initial, backup, files = base / 'initial_visual_reviews', base / 'backup', base / 'files'
    initial.mkdir(); backup.mkdir(); files.mkdir()
    old_rows, new_rows, saved_rows = [], [], []
    for label, parts in PARTS.items():
        count = {'article': 18, 'manuscript': 197, 'supplement': 198}[label]
        (backup / label).mkdir(); (files / label).mkdir()
        src = files / label / 'source.docx'; src.write_bytes(b'current-source-' + label.encode())
        pdf = files / label / 'source.pdf'; pdf.write_bytes(b'current-pdf-' + label.encode())
        old_pdf = backup / label / 'source.pdf'; old_pdf.write_bytes(b'old-pdf-' + label.encode())
        old_pdf_id = identity(old_pdf); old_pdf_id['path'] = str(pdf)
        source = identity(src)
        old_source = dict(source); old_source['sha256'] = hashlib.sha256(b'old-source-' + label.encode()).hexdigest()
        old_images, new_images = [], []
        for p in range(1, count + 1):
            filename = f'page-{p}.png'; img = files / label / filename; saved = backup / label / filename
            old_data = f'old-{label}-{p}'.encode(); saved.write_bytes(old_data)
            img.write_bytes(old_data + (b'-new' if p in FRESH[label] else b''))
            old_id = identity(saved); old_id['path'] = str(img)
            old_images.append(old_id); new_images.append(identity(img))
            saved_rows.append({'original':str(img), 'backup':str(saved),'sha256':identity(saved)['sha256']})
        previous = {'label':label,'pages':count,'source':old_source,'rendered_pdf':old_pdf_id,'page_images':old_images}
        current = {'label':label,'pages':count,'source':source,'rendered_pdf':identity(pdf),'page_images':new_images}
        old_rows.append(previous); new_rows.append(current)
        for filename, first, last, reviewer in parts:
            pages = list(range(first,last+1))
            record = {'label':label,'status':'bounded_pass','reviewer':reviewer,'findings':[],
                      'source':old_source,'rendered_pdf':old_pdf_id,'pages':count,
                      'original_detail_pages_inspected':pages,
                      'page_images_inspected':[old_images[p-1] for p in pages]}
            write(initial / filename, record)
            (base / filename).write_bytes(b'ORIGINAL REVIEW SENTINEL')
        if FRESH[label]:
            followup = {'label':label,'status':'bounded_pass','reviewer':'/root','findings':[],
                        'source':source,'rendered_pdf':identity(pdf),'pages':count,
                        'original_detail_pages_inspected':FRESH[label],
                        'page_images_inspected':[new_images[p-1] for p in FRESH[label]]}
            write(base / f'visual_{label}_followup_pages.json', followup)
    write(initial / 'render_results.json', old_rows); write(base / 'render_results.json', new_rows)
    write(initial / 'snapshot_locations.json', {'png_backup':str(backup),'page_images':saved_rows})
    (base / 'visual_reconciliation_results.json').write_bytes(b'ORIGINAL REPORT SENTINEL')


def edit_json(path, function):
    data = read(path); function(data); write(path, data)


def scratch_probes():
    source = SCRIPT.read_text()
    probes = [
        ('missing_fresh_record', lambda b: (b/'visual_manuscript_followup_pages.json').unlink()),
        ('missing_changed_page', lambda b: edit_json(b/'visual_manuscript_followup_pages.json', lambda j: j['original_detail_pages_inspected'].pop())),
        ('stale_fresh_source', lambda b: edit_json(b/'visual_manuscript_followup_pages.json', lambda j: j['source'].update(sha256='0'*64))),
        ('wrong_fresh_label', lambda b: edit_json(b/'visual_manuscript_followup_pages.json', lambda j: j.update(label='supplement'))),
        ('duplicate_fresh_image', lambda b: edit_json(b/'visual_manuscript_followup_pages.json', lambda j: j['page_images_inspected'].append(j['page_images_inspected'][0]))),
        ('current_image_corrupted', lambda b: (b/'files/supplement/page-198.png').write_bytes(b'corrupt')),
        ('old_image_corrupted', lambda b: (b/'backup/article/page-1.png').write_bytes(b'corrupt')),
        ('old_pdf_corrupted', lambda b: (b/'backup/supplement/source.pdf').write_bytes(b'corrupt')),
        ('duplicate_initial_render_label', lambda b: edit_json(b/'initial_visual_reviews/render_results.json', lambda j: j.append(j[0]))),
        ('duplicate_new_page', lambda b: edit_json(b/'render_results.json', lambda j: j[2]['page_images'].append(j[2]['page_images'][0]))),
        ('duplicate_initial_review_page', lambda b: edit_json(b/'initial_visual_reviews/visual_supplement_part_101_198.json', lambda j: j['original_detail_pages_inspected'].append(101))),
        ('wrong_initial_reviewer', lambda b: edit_json(b/'initial_visual_reviews/visual_article_review.json', lambda j: j.update(reviewer='/root/other'))),
        ('initial_findings_not_clear', lambda b: edit_json(b/'initial_visual_reviews/visual_supplement_part_101_198.json', lambda j: j['findings'].append('defect'))),
        ('stale_initial_image', lambda b: edit_json(b/'initial_visual_reviews/visual_manuscript_part_101_150.json', lambda j: j['page_images_inspected'][0].update(sha256='0'*64))),
        ('unexpected_unchanged_followup', lambda b: write(b/'visual_article_followup_pages.json', {'label':'article'})),
        ('page_count_changed', lambda b: edit_json(b/'render_results.json', lambda j: j[1].update(pages=198))),
    ]
    outcomes = []
    for name, mutation in [('valid_413_page_chain', None)] + probes:
        with tempfile.TemporaryDirectory(prefix='pf8-independent-reconcile-', dir='/private/tmp') as tmp:
            base = Path(tmp); make_fixture(base)
            protected = [base / n for parts in PARTS.values() for n, *_ in parts]
            protected.append(base / 'visual_reconciliation_results.json')
            before = {str(p): p.read_bytes() for p in protected}
            if mutation: mutation(base)
            namespace = {'__file__':str(SCRIPT),'__name__':'independent_scratch_reconciliation'}
            exec(compile(source, str(SCRIPT), 'exec'), namespace)
            namespace['OUT'], namespace['INITIAL'] = base, base / 'initial_visual_reviews'
            error = None
            try:
                with redirect_stdout(io.StringIO()): namespace['main']()
            except (AssertionError, KeyError, FileNotFoundError, ValueError) as exc:
                error = type(exc).__name__ + ': ' + str(exc)
            if mutation:
                assert error is not None, name
                assert all(p.read_bytes() == before[str(p)] for p in protected), name
            else:
                assert error is None, error
                assert read(base/'visual_reconciliation_results.json')['retained_identical_page_count'] == 405
            outcomes.append({'name':name,'status':'pass','expected_rejection':bool(mutation),
                             'all_seven_existing_outputs_unchanged_on_rejection':bool(mutation),
                             'exception':error})
    completed = subprocess.run([sys.executable,'-I','-O',str(SCRIPT)],capture_output=True,text=True)
    assert completed.returncode != 0 and 'Validation assertions must remain enabled.' in completed.stderr
    outcomes.append({'name':'optimized_python_refuses_before_read_or_write','status':'pass'})
    return outcomes


def main():
    if not __debug__: raise RuntimeError('Independent audit requires validation assertions.')
    protected = [ROOT / n for parts in PARTS.values() for n, *_ in parts]
    protected += [ROOT/'visual_reconciliation_results.json', ROOT/'render_results.json']
    before = {str(p):identity(p) for p in protected}
    actual = actual_audit()
    probes = scratch_probes()
    assert all(identity(p)==before[str(p)] for p in protected)
    results = {'generated_utc':datetime.now(timezone.utc).isoformat(),'status':'bounded_pass',
               'script':identity(SCRIPT),'driver':identity(__file__),
               'actual_chain':actual,'scratch_probe_count':len(probes),'scratch_probes':probes,
               'real_reconciliation_outputs_unmodified':True}
    output = ROOT/'independent_visual_reconciliation_results.json'
    assert not output.exists()
    write(output, results)
    print(json.dumps({'status':results['status'],'actual_pages':413,'scratch_probes':len(probes),'results':identity(output)}))


if __name__ == '__main__': main()
