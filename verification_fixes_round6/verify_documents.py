#!/usr/bin/env python3
"""Verify actual document changes, untouched scientific inputs and helper evidence."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
GIT = '/Users/samnimoh/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/git'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else None


def doc(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        tree = ET.fromstring(z.read('word/document.xml'))
        paras = [''.join(n.text or '' for n in p.iter(W + 't')) for p in tree.iter(W + 'p')]
        media = {p: hashlib.sha256(z.read(p)).hexdigest() for p in z.namelist() if p.startswith('word/media/') and not p.endswith('/')}
        return paras, Counter(n.tag for n in tree.iter()), media


def main():
    original = subprocess.check_output([GIT, 'show', 'd59bbf6:Pf8_Ghana_manuscript_REVISED.docx'], cwd=ROOT)
    old, old_shape, old_media = doc(original)
    current_path = ROOT / 'Pf8_Ghana_manuscript_REVISED.docx'
    new, new_shape, new_media = doc(current_path.read_bytes())
    plan = json.loads((OUT / 'accepted_document_edits.json').read_text())
    followup = json.loads((OUT / 'final_document_additional_edits.json').read_text())
    expected = old.copy()
    number = re.compile(r'\d+(?:[.,]\d+)*')
    edits = plan['manuscript_edits'] + followup['manuscript_edits']
    for e in edits:
        i = e['paragraph_index']
        assert expected[i].count(e['quote']) == 1, i
        expected[i] = expected[i].replace(e['quote'], e['repl'])
    checks = {'manuscript_exactly_matches_reviewed_edits': new == expected,
        'manuscript_xml_structure_preserved': old_shape == new_shape,
        'manuscript_figure_bytes_preserved': old_media == new_media,
        'scientific_numerical_tokens_preserved': Counter(number.findall('\n'.join(old))) - Counter(number.findall('\n'.join(new))) == Counter({'6.8': 1}) and
            not Counter(number.findall('\n'.join(new))) - Counter(number.findall('\n'.join(old)))}
    layout_path = OUT / 'heading_layout_results.json'
    if layout_path.exists():
        layout = json.loads(layout_path.read_text())
        with zipfile.ZipFile(io.BytesIO(original)) as archive:
            expected_styles = archive.read('word/styles.xml').decode()
        for change in layout['changes']:
            assert expected_styles.count(change['before_xml']) == 1
            assert change['after_xml'] == change['before_xml'].replace('<w:pPr>', '<w:pPr><w:keepNext/><w:keepLines/>', 1)
            expected_styles = expected_styles.replace(change['before_xml'], change['after_xml'], 1)
        with zipfile.ZipFile(current_path) as archive:
            checks['manuscript_styles_have_only_reviewed_heading_flags'] = archive.read('word/styles.xml').decode() == expected_styles
    article_before = subprocess.check_output([GIT, 'show', 'd59bbf6:article/article.md'], cwd=ROOT).decode()
    expected_md = article_before
    for e in plan['article_edits']:
        assert expected_md.count(e['quote']) == 1
        expected_md = expected_md.replace(e['quote'], e['repl'])
    checks['article_source_exactly_matches_reviewed_edits'] = expected_md == (ROOT / 'article/article.md').read_text()
    supp_path = ROOT / 'article/Additional_file_1.docx'
    supp, _, supp_media = doc(supp_path.read_bytes())
    checks['supplement_figure_bytes_preserved'] = supp_media == old_media
    labels = {kind: [m[1] for p in supp if (m := re.match(rf'^{kind}\s+(S\d+)\.', p))] for kind in ('Figure', 'Table')}
    checks['supplement_captions_unique_contiguous'] = labels['Figure'] == [f'S{i}' for i in range(1, 24)] and labels['Table'] == [f'S{i}' for i in range(1, 53)]
    for name, paragraphs in [('main', new), ('supplement', supp)]:
        text = '\n'.join(paragraphs)
        cascade = next(p for p in paragraphs if 'The cascade, defined once' in p)
        checks[name + '_unsupported_cascade_reference_removed'] = not re.search(r'Table (?:6\.8|S29)', cascade)
        checks[name + '_caption_fragments_removed'] = 'This table is new in this revision and is.' not in text
        checks[name + '_stale_current_git_status_removed'] = not re.search(r'project is not under version control', text, re.I)
        checks[name + '_graph_confidence_is_conditional'] = 'Conditional support for improved fit in the selected covariance model' in text
        checks[name + '_live_panmixia_estimate_claim_removed'] = 'the panmixia estimate was always well determined' not in text
    inventory = json.loads((ROOT / 'verification_review_round6/change_inventory.json').read_text())
    allowed = {str(ROOT / p) for p in ('Pf8_Ghana_manuscript_REVISED.docx', 'Pf8_Ghana_manuscript_REVISED.pdf',
        'article/Additional_file_1.docx', 'article/Additional_file_1.pdf', 'article/Pf8_Ghana_article.docx',
        'article/Pf8_Ghana_article.pdf', 'article/article.md', 'tools/README.md', 'tools/apply_edits.py',
        'tools/build_article.py', 'tools/make_supplement.py', 'provenance_final/VERIFICATION_NOTES.md')}
    untouched = [r for r in inventory['files'] + inventory['new_source_files'] if r['path'] not in allowed]
    unexpected = [r['path'] for r in untouched if sha(Path(r['path'])) != r['sha256']]
    checks['scientific_sources_outputs_and_prior_reviews_unchanged'] = not unexpected
    notes_before = subprocess.check_output([GIT, 'show', 'd59bbf6:provenance_final/VERIFICATION_NOTES.md'], cwd=ROOT).decode()
    notes_after = (ROOT / 'provenance_final/VERIFICATION_NOTES.md').read_text()
    checks['earlier_verification_notes_preserved_before_new_entry'] = notes_after.startswith(notes_before)
    editor = json.loads((OUT / 'editor_regression_results.json').read_text())
    builder = json.loads((OUT / 'builder_test_results.json').read_text())
    checks['editor_49_regressions_pass_for_final_source'] = editor['passed'] == 49 and editor['script_sha256'] == sha(ROOT / 'tools/apply_edits.py') and all(e['status'] == 'passed' for e in editor['tests'])
    checks['builder_38_regressions_pass_for_final_source'] = builder['all_passed'] and len(builder['results']) == 38 and builder['builder_sha256_after'] == sha(ROOT / 'tools/build_article.py')
    layout_tests = json.loads((OUT / 'independent_builder_layout_followup.json').read_text())
    checks['builder_15_independent_layout_package_checks_pass'] = (layout_tests['all_passed']
        and layout_tests['test_count'] == 15
        and layout_tests['builder_sha256_before'] == layout_tests['builder_sha256_after'] == sha(ROOT / 'tools/build_article.py')
        and all(row['passed'] for row in layout_tests['tests']))
    for name in ('editor', 'builder'):
        evidence = json.loads((OUT / f'independent_{name}_followup.json').read_text())
        target = ROOT / 'tools' / ('apply_edits.py' if name == 'editor' else 'build_article.py')
        before = evidence.get('script_sha256_before', evidence.get('builder_sha256_before'))
        after = evidence.get('script_sha256_after', evidence.get('builder_sha256_after'))
        outcomes = evidence.get('results', evidence.get('tests'))
        checks[name + '_independent_final_version_passes'] = before == after == sha(target) and all(e['passed'] for e in outcomes)
    record = {'generated_utc': datetime.now(timezone.utc).isoformat(), 'checks': checks,
        'assertion_scope': 'Exact intended editorial changes, package preservation, current helper regression evidence and untouched scientific identities; not statistical or implementation-proof certification.',
        'manuscript_substitutions': len(edits), 'article_substitutions': len(plan['article_edits']),
        'unaffected_identities_checked': len(untouched), 'unexpected_changes': unexpected,
        'current_document_hashes': {str(p): sha(p) for p in (current_path, supp_path, ROOT / 'article/Pf8_Ghana_article.docx')},
        'supplement_labels': labels}
    (OUT / 'document_validation.json').write_text(json.dumps(record, indent=2) + '\n')
    failed = [k for k, value in checks.items() if not value]
    print(json.dumps({'passed': sum(checks.values()), 'total': len(checks), 'failed': failed}))
    return bool(failed)


if __name__ == '__main__':
    raise SystemExit(main())
