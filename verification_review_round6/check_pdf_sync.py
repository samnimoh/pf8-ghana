#!/usr/bin/env python3
"""Compare every supplied PDF page text with a fresh conversion."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re

OUT=Path(__file__).resolve().parent


def norm(value):
    return re.sub(r'\s+','',re.sub(r'Page\s+\d+\s+of\s+\d+','',value))


def identity(path):
    data=path.read_bytes()
    return {'path':str(path),'bytes':len(data),'sha256':hashlib.sha256(data).hexdigest()}


def main():
    conversions=json.loads((OUT/'render_conversion.json').read_text())
    results=[]
    for c in conversions:
        label=c['label']
        fresh=(OUT/f'{label}_fresh_pdf_text.txt').read_text().split('\f')[:-1]
        provided=(OUT/f'{label}_supplied_pdf_text.txt').read_text().split('\f')[:-1]
        comparisons=[{'page':i+1,'matches_after_whitespace_footer_normalization':norm(a)==norm(b)} for i,(a,b) in enumerate(zip(fresh,provided))]
        evidence=[]
        for phrase in ('because proper matching lowers the threshold','does not establish the direction of the error for the final',
                       'remaining four fall at genuinely off-anchor','not identified directions of historical exchange',
                       'What the graph establishes is that a strictly bifurcating tree','weakly inverts it'):
            pages=[i+1 for i,p in enumerate(fresh) if norm(phrase) in norm(p)]
            if pages:
                evidence.append({'phrase':phrase,'fresh_pages':pages})
        results.append({'label':label,'docx':identity(Path(c['docx'])),'supplied_pdf':identity(Path(c['supplied_pdf'])),
                        'fresh_pdf':identity(Path(c['fresh_pdf'])),'fresh_pages':len(fresh),'supplied_pages':len(provided),
                        'all_page_texts_match':len(fresh)==len(provided) and all(x['matches_after_whitespace_footer_normalization'] for x in comparisons),
                        'page_comparisons':comparisons,'evidence_locations':evidence,'rasterized_review_pages':c['rasterized_review_pages']})
        print(label,len(fresh),len(provided),'all match',results[-1]['all_page_texts_match'])
    report={'generated_utc':datetime.now(timezone.utc).isoformat(),'comparisons':results,
            'comparison_scope':'All 413 PDF page texts, ignoring whitespace and page-count footers; only selected page images receive visual inspection.'}
    (OUT/'render_review.json').write_text(json.dumps(report,indent=2,ensure_ascii=False)+'\n')
    return 0 if all(r['all_page_texts_match'] for r in results) else 1


if __name__=='__main__':
    raise SystemExit(main())
