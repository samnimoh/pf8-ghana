#!/usr/bin/env python3
"""Independent read-only check of the corrected document text and packages."""
from pathlib import Path
import collections
import hashlib
import io
import json
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
BASE = 'd59bbf6722c36b8f8f09e707a2290fbb699ed83f'
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
GIT = '/Users/samnimoh/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/git'


def git(*args):
    return subprocess.check_output([GIT, '-C', str(ROOT), *args])


def sha(data):
    return hashlib.sha256(data).hexdigest()


def read_doc(data):
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        xml = archive.read('word/document.xml')
        members = {item.filename: archive.read(item.filename) for item in archive.infolist()}
        assert archive.testzip() is None
    tree = ET.fromstring(xml)
    paragraphs = [''.join(t.text or '' for t in p.iter(W+'t')) for p in tree.iter(W+'p')]
    return paragraphs, members


def apply_expected(paragraphs, edits):
    expected = paragraphs[:]
    for edit in edits:
        hits = [i for i, p in enumerate(expected) if edit['quote'] in p]
        assert len(hits) == edit.get('expected_count', 1), (edit['quote'], hits)
        for i in hits:
            assert expected[i].count(edit['quote']) == 1
            expected[i] = expected[i].replace(edit['quote'], edit['repl'], 1)
    return expected


def normalize_references(text):
    return re.sub(r'\b(Figure|Table) (?:S\d+|[0-9A-F]+\.\d+[a-z]?)(?!\d)(?![a-z])(?!\.\d)', r'\1 REFERENCE', text)


def numeric_tokens(text):
    return re.findall(r'\d+(?:[.,]\d+)*(?:[eE][+-]?\d+)?', text)


def heading_style_delta(old_styles, new_styles, document_xml):
    expected = old_styles
    for style_id in ('Heading1', 'Heading2', 'Heading3'):
        pattern = re.compile(rb'<w:style\b[^>]*\bw:styleId="'+style_id.encode()+rb'"[^>]*>.*?</w:style>', re.S)
        hits = list(pattern.finditer(expected))
        if len(hits)!=1 or hits[0].group().count(b'<w:pPr>')!=1:
            return {'exact_three_style_delta':False}
        match = hits[0]
        replacement = match.group().replace(b'<w:pPr>', b'<w:pPr><w:keepNext/><w:keepLines/>', 1)
        expected = expected[:match.start()]+replacement+expected[match.end():]
    counts = collections.Counter()
    direct_flags = []
    tree = ET.fromstring(document_xml)
    for i,p in enumerate(tree.iter(W+'p')):
        properties = p.find(W+'pPr')
        style = properties.find(W+'pStyle') if properties is not None else None
        identifier = style.get(W+'val') if style is not None else None
        if identifier in ('Heading1','Heading2','Heading3'):
            counts[identifier] += 1
            if properties.find(W+'keepNext') is not None or properties.find(W+'keepLines') is not None:
                direct_flags.append(i)
    return {'exact_three_style_delta':expected==new_styles,
            'old_styles_sha256':sha(old_styles),'new_styles_sha256':sha(new_styles),
            'affected_style_ids':['Heading1','Heading2','Heading3'],
            'paragraphs_using_each_style':dict(counts),'direct_heading_flag_override_paragraph_indices':direct_flags,
            'scope':'Exactly keepNext/keepLines inserted in the three named style pPr elements; all other style bytes compared unchanged.'}


def main():
    paths = ['Pf8_Ghana_manuscript_REVISED.docx', 'article/Additional_file_1.docx',
             'article/Pf8_Ghana_article.docx', 'article/article.md', 'article/CANONICAL_FACTS_FOR_ARTICLE.md',
             'provenance_final/VERIFICATION_NOTES.md', 'tools/build_article.py']
    identities = {path: sha((ROOT/path).read_bytes()) for path in paths}
    plan = json.loads((OUT/'accepted_document_edits.json').read_text())
    original, old_members = read_doc(git('show', BASE+':'+paths[0]))
    current, new_members = read_doc((ROOT/paths[0]).read_bytes())
    supplement, supplement_members = read_doc((ROOT/paths[1]).read_bytes())
    article, article_members = read_doc((ROOT/paths[2]).read_bytes())
    expected = apply_expected(original, plan['manuscript_edits'])
    additional_path = OUT/'final_document_additional_edits.json'
    additional_applied = False
    if additional_path.exists():
        additional = json.loads(additional_path.read_text())['manuscript_edits']
        if all(any(edit['repl'] in paragraph for paragraph in expected) for edit in additional):
            additional_applied = current == expected
        else:
            additional_expected = apply_expected(expected, additional)
            if current == additional_expected:
                expected = additional_expected
                additional_applied = True
    numerical_changes = []
    for edit in plan['manuscript_edits'] + plan['article_edits']:
        old_numbers, new_numbers = numeric_tokens(edit['quote']), numeric_tokens(edit['repl'])
        if old_numbers != new_numbers:
            numerical_changes.append({'paragraph_index':edit.get('paragraph_index'),
                                      'quote_numbers':old_numbers,'replacement_numbers':new_numbers,
                                      'quote':edit['quote'],'repl':edit['repl']})
    only_reference_number_removed = (
        len(numerical_changes) == 1
        and numerical_changes[0]['quote_numbers'] == ['6.8', '10.1']
        and numerical_changes[0]['replacement_numbers'] == ['10.1']
    )
    if additional_applied:
        assert all(numeric_tokens(edit['quote']) == numeric_tokens(edit['repl']) for edit in additional)
    text_comparison = current == expected
    mismatches = [{'paragraph_index': i, 'expected': a, 'actual': b}
                  for i, (a, b) in enumerate(zip(expected, current)) if a != b]
    style_delta = heading_style_delta(old_members['word/styles.xml'], new_members['word/styles.xml'], new_members['word/document.xml'])
    unaffected_parts = {name: (style_delta['exact_three_style_delta'] if name=='word/styles.xml' else sha(value) == sha(new_members.get(name, b'')))
                        for name, value in old_members.items() if name != 'word/document.xml'}
    editorial_xml_identity = json.loads((OUT/'document_followup_edit_results.json').read_text())['document_xml_after_sha256']
    old_md = git('show', BASE+':article/article.md').decode()
    expected_md = old_md
    for edit in plan['article_edits']:
        assert expected_md.count(edit['quote']) == edit.get('expected_count', 1)
        expected_md = expected_md.replace(edit['quote'], edit['repl'])
    new_md = (ROOT/'article/article.md').read_text()
    old_article, _ = read_doc(git('show', BASE+':'+paths[2]))
    doc_article_edits = [{**edit, 'quote': re.sub(r'^#+ ', '', edit['quote']).replace('~',''),
                         'repl': re.sub(r'^#+ ', '', edit['repl']).replace('~','')}
                        for edit in plan['article_edits']]
    expected_article = apply_expected(old_article, doc_article_edits)
    article_comparison = article == expected_article
    aligned = []
    j = 0
    extra = []
    for i, p in enumerate(current):
        # Four front-matter substitutions plus four inserted supplementary preamble paragraphs.
        while j < len(supplement) and supplement[j].startswith(('What this document is.', 'Numbering.', 'References.', 'Where to look.')):
            extra.append(j)
            j += 1
        q = supplement[j]
        if normalize_references(p) != normalize_references(q):
            aligned.append({'manuscript_paragraph_index': i, 'supplement_paragraph_index': j,
                            'manuscript': p, 'supplement': q})
        j += 1
    caps = {'Figure': [], 'Table': []}
    for p in supplement:
        match = re.match(r'^(Figure|Table) S(\d+)\.', p)
        if match:
            caps[match[1]].append(int(match[2]))
    live_version = [{'paragraph_index': i, 'text': p} for i, p in enumerate(current)
                    if 'the project is not under version control' in p.lower()]
    fragment = [{'paragraph_index': i, 'text': p} for i, p in enumerate(current)
                if 'This table is new in this revision and is.' in p]
    cascade = [p for p in current if 'The cascade, defined once.' in p]
    panmixia = [{'paragraph_index': i, 'text': p} for i, p in enumerate(current)
                if re.search(r'panmix|random mating|mating system', p, re.I)]
    notes_path = 'provenance_final/VERIFICATION_NOTES.md'
    old_notes = git('show', BASE+':'+notes_path)
    new_notes = (ROOT/notes_path).read_bytes()
    builder_layout = json.loads((OUT/'independent_builder_layout_followup.json').read_text())
    builder_followup = json.loads((OUT/'independent_builder_followup.json').read_text())
    final_builder_sha = identities['tools/build_article.py']
    builder_test_source_matches = all(report['builder_sha256_before']==report['builder_sha256_after']==final_builder_sha
                                     and report['all_passed'] for report in (builder_layout, builder_followup))
    layout_article = next(row for row in builder_layout['tests'] if row['name']=='actual_article_matches_final_builder_content')
    scientific_changes = [name for name in git('diff', '--name-only', BASE, '--').decode().splitlines()
                          if name != notes_path and (name.startswith(('corrected/', 'provenance_final/', 'figures/'))
                          or name == 'article/CANONICAL_FACTS_FOR_ARTICLE.md')]
    results = {
        'scope': 'Read-only final text/package review. Root performs PDF rendering and visual QA. No scientific pipeline or biological calculation executed.',
        'reviewer': 'final_document_check',
        'git_head_at_check': git('rev-parse','HEAD').decode().strip(),
        'baseline_commit': BASE,
        'source_sha256': identities,
        'checks': {
            'manuscript_exactly_matches_accepted_edits': text_comparison,
            'additional_six_proposals_applied': additional_applied,
            'manuscript_paragraph_count_unchanged': len(current) == len(original),
            'unrelated_manuscript_package_parts_preserved': all(unaffected_parts.values()),
            'article_markdown_exactly_matches_four_accepted_edits': expected_md == new_md,
            'article_docx_paragraphs_exactly_match_four_accepted_edits': article_comparison,
            'supplement_extra_preamble_paragraphs': len(extra),
            'supplement_differences_other_than_numbering_and_front_matter': len(aligned),
            'supplement_table_labels_contiguous_unique': caps['Table'] == list(range(1,53)),
            'supplement_figure_labels_contiguous_unique': caps['Figure'] == list(range(1,24)),
            'known_caption_fragments_absent': not fragment,
            'unsupported_cascade_Table_6_8_pointer_removed': len(cascade)==1 and 'Table 6.8' not in cascade[0],
            'live_not_under_version_control_assertions_absent': not live_version,
            'canonical_facts_and_saved_scientific_inputs_outputs_unchanged': not scientific_changes,
            'replacement_numeric_tokens_unchanged_except_removed_unsupported_reference': only_reference_number_removed,
            'existing_provenance_notes_preserved_with_correction_appendix_only': new_notes.startswith(old_notes),
            'manuscript_heading_style_delta_exact_and_scoped': style_delta['exact_three_style_delta'],
            'manuscript_heading_direct_overrides_absent': not style_delta.get('direct_heading_flag_override_paragraph_indices'),
            'manuscript_document_XML_identical_to_accepted_editorial_revision': sha(new_members['word/document.xml'])==editorial_xml_identity,
            'derivative_style_bytes_identical_to_manuscript': supplement_members['word/styles.xml']==new_members['word/styles.xml']==article_members['word/styles.xml'],
            'independent_builder_regressions_match_final_source': builder_test_source_matches,
            'actual_article_identity_matches_independent_layout_recheck': layout_article['passed'] and layout_article['actual_article_sha256']==identities['article/Pf8_Ghana_article.docx'],
        },
        'edit_plan_sha256': sha((OUT/'accepted_document_edits.json').read_bytes()),
        'additional_edit_plan_sha256': sha(additional_path.read_bytes()) if additional_path.exists() else None,
        'numeric_token_edit_exceptions': numerical_changes,
        'manuscript_unexpected_paragraph_differences': mismatches,
        'supplement_alignment_differences': aligned,
        'live_version_control_assertions': live_version,
        'remaining_panmixia_mating_mentions': panmixia,
        'scientific_file_changes': scientific_changes,
        'provenance_note_change': {'path':notes_path,'old_sha256':sha(old_notes),'new_sha256':sha(new_notes),
                                  'scope':'Appended correction record; no prior note text changed.' if new_notes.startswith(old_notes) else 'Unexpected existing-note modification.'},
        'intentional_heading_style_delta':style_delta,
        'manuscript_editorial_XML_sha256':editorial_xml_identity,
        'manuscript_final_XML_sha256':sha(new_members['word/document.xml']),
        'final_builder_followup':{'builder_sha256':final_builder_sha,'independent_alias_package_checks':builder_followup['test_count'],
                                  'independent_layout_package_failure_checks':builder_layout['test_count'],
                                  'source_matched_and_all_passed':builder_test_source_matches},
        'manual_review': {
            'panmixia_mating_assertions': 'Remaining mentions are explicit exclusions or previous-version history; no live inference of panmixia or random mating located.',
            'unconditional_TreeMix_history_or_exchange_claims': 'Methods, summary cells and conclusions qualify improved covariance fit and conditional edge statistics; original gene-flow thesis objective is preserved and its answered status narrowed.',
            'remaining_practical_consequence_claims': ('The two proposed propagation omissions at paragraph indices 3183 and 3649 are corrected in the actual final manuscript and supplement.'
                                                     if additional_applied else 'Two propagation omissions were proposed for root correction at paragraph indices 3183 and 3649.'),
            'historical_withdrawals': 'Historical quotations, discarded panmixia wording and original thesis objectives retained with explicit caveats.',
            'number_integrity': 'Expected accepted replacements preserve scientific quantities; only the unsupported Table 6.8 reference is removed. Scientific inputs and outputs checked by unchanged Git file identity, without recomputation.'
        },
        'findings': [],
        'resolved_during_final_review': ({'Git_status_paragraph_indices':[3521,3522,3965,4033],
                                         'practical_consequences_paragraph_index':3183,
                                         'sampling_design_paragraph_index':3649,
                                         'resolution_verified_in_actual_DOCX':True}
                                        if additional_applied else {}),
        'limits': ['PDFs not reviewed by this agent while regeneration was in progress.',
                   'Review verifies the scoped corrections and edit integrity, not all citations or every scientific inference in the full record.',
                   'No new Lean implementation proof or end-to-end scientific pipeline validation performed.']
    }
    if not additional_applied:
        results['findings'] = [
            {'priority':'P3','concept':'Git-status propagation','paragraph_indices':[3521,3522,3965,4033],
             'description':'Four live passages still treat absence of version control as current; current Git does not itself establish exact historical generating state.'},
            {'priority':'P2','concept':'Practical-consequence propagation','paragraph_indices':[3183],
             'description':'The operational-irrelevance claim survives although practical consequences were not tested and equivalent interpretations were narrowed elsewhere.'},
            {'priority':'P2','concept':'Sampling-design propagation','paragraph_indices':[3649],
             'description':'A next-step paragraph still derives the surveillance-design implication from differentiation magnitude alone although sampling adequacy was not evaluated.'}
        ]
    boolean_checks_pass = all(value for value in results['checks'].values() if isinstance(value, bool))
    results['status'] = 'bounded_pass' if boolean_checks_pass and additional_applied and len(aligned)==3 and len(extra)==4 else 'needs_followup'
    (OUT/'final_document_review.json').write_text(json.dumps(results, indent=2, ensure_ascii=False)+'\n')
    print(json.dumps({'status':results['status'],'checks':results['checks'],'findings':results['findings'],
                      'supplement_alignment_difference_indices':[(x['manuscript_paragraph_index'],x['supplement_paragraph_index']) for x in aligned]},indent=2))


if __name__ == '__main__':
    main()
