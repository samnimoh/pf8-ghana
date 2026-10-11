#!/usr/bin/env python3
"""Merge independently reviewed edits and assert targets/numerical preservation."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
W = '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    proposals = json.loads((OUT / 'document_proposals.json').read_text())
    review = json.loads((OUT / 'document_proposal_refutation.json').read_text())
    assert review['proposal_sha256'] == sha(OUT / 'document_proposals.json')
    assert all(e['decision'] in ('accept', 'accept_with_amendment') and e['quote_matches_stated_target'] for e in review['decisions'])
    assert all(sha(Path(path)) == expected for path, expected in proposals['source_hashes'].items())
    main_path = ROOT / 'Pf8_Ghana_manuscript_REVISED.docx'
    with zipfile.ZipFile(main_path) as z:
        tree = ET.fromstring(z.read('word/document.xml'))
    paragraphs = [''.join(t.text or '' for t in p.iter(W + 't')) for p in tree.iter(W + 'p')]
    originals = {e['paragraph_index']: e for e in proposals['edits'] if e['source'] == str(main_path)}
    for merged in review['additional_gaps_and_merged_replacements']:
        assert merged['source'] == str(main_path)
        originals[merged['paragraph_index']] = dict(merged, concept='reviewed interpretation/provenance amendment', sev=merged['priority'])
    edits = [originals[index] for index in sorted(originals)]
    number = re.compile(r'\d+(?:[.,]\d+)*')
    for edit in edits:
        assert paragraphs[edit['paragraph_index']].count(edit['quote']) == 1, edit['paragraph_index']
        assert sum(p.count(edit['quote']) for p in paragraphs) == edit['expected_count'] == 1
        before, after = Counter(number.findall(edit['quote'])), Counter(number.findall(edit['repl']))
        if edit['concept'] == 'cross-reference':
            assert before - after == Counter({'6.8': 1}) and not after - before
        else:
            assert before == after, edit['paragraph_index']
    article_edits = [e for e in proposals['edits'] if e['source'] == str(ROOT / 'article/article.md')]
    markdown = (ROOT / 'article/article.md').read_text()
    for edit in article_edits:
        assert markdown.count(edit['quote']) == edit['expected_count'] == 1
        assert Counter(number.findall(edit['quote'])) == Counter(number.findall(edit['repl']))
    plan = {'scope': 'Resolve round-six interpretation, cross-reference and caption findings, including independently confirmed propagation omissions and stale Git status.',
        'manuscript_before_sha256': sha(main_path), 'article_md_before_sha256': sha(ROOT / 'article/article.md'),
        'manuscript_edits': edits, 'article_edits': article_edits,
        'proposal_sha256': sha(OUT / 'document_proposals.json'),
        'refutation_sha256': sha(OUT / 'document_proposal_refutation.json'),
        'all_targets_unique': True, 'scientific_numerical_tokens_preserved': True,
        'numeric_reference_exception': 'One unsupported Table 6.8 pointer removed.',
        'remaining_panmixia_mentions': review['remaining_panmixia_mentions_after_merged_edits']}
    (OUT / 'accepted_document_edits.json').write_text(json.dumps(plan, indent=2, ensure_ascii=False) + '\n')
    print(json.dumps({'manuscript_paragraphs': len(edits), 'article_edits': len(article_edits), 'all_targets_unique': True, 'scientific_numbers_preserved': True}))


if __name__ == '__main__':
    main()
