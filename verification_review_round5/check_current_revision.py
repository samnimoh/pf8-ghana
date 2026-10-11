#!/usr/bin/env python3
"""Verify reported corrections using current document text and saved aggregates."""
import csv
from datetime import datetime, timezone
import hashlib
import io
import json
from pathlib import Path
import re
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
GIT = "/Users/samnimoh/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback/git"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
SOURCES = {
    "article": "article/Pf8_Ghana_article.docx", "article_md": "article/article.md",
    "facts": "article/CANONICAL_FACTS_FOR_ARTICLE.md",
    "main": "Pf8_Ghana_manuscript_REVISED.docx", "supplement": "article/Additional_file_1.docx",
    "notes": "provenance_final/VERIFICATION_NOTES.md", "readme": "provenance_final/audit_scripts/README.md",
    "n1900_alias": "corrected/dimred_comparison_n1900_analysisset.csv",
    "n4905_alias": "corrected/dimred_comparison_n4905_qcpassset.csv",
    "saved_1900": "corrected/dimred_comparison_qcset.csv",
    "saved_4905": "evaluation/server_snapshot/results/dimred_comparison.csv",
    "saved_4905_log": "evaluation/server_snapshot/logs/step03_dimred.log",
    "warning": "corrected/DIMRED_FILENAME_WARNING.md",
    "figure": "corrected/dimred_comparison_zone_qcset.png",
    "lean_validation": "verification_audit/lean_validation.json",
}


def sha(data):
    return hashlib.sha256(data).hexdigest()


def text(node):
    return "".join(x.text or "" for x in node.iter(W + "t")).strip()


def doc(data):
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        body = ET.fromstring(z.read("word/document.xml")).find(W + "body")
        return {"paragraphs": [text(p) for p in body if p.tag == W + "p"],
                "media": [{"member": p, "sha256": sha(z.read(p))}
                          for p in z.namelist() if p.startswith("word/media/")]}


def csv_rows(data):
    return {r["method"]: r for r in csv.DictReader(io.StringIO(data.decode()))}


def match(literal, value):
    digits = len(literal.split('.',1)[1]) if '.' in literal else 0
    return float(literal) == round(float(value), digits)


def git(*args):
    return subprocess.run([GIT, *args], cwd=ROOT, capture_output=True, check=True).stdout


def main():
    blobs = {k: (ROOT / rel).read_bytes() for k,rel in SOURCES.items()}
    inputs = {k: {"path": str(ROOT / SOURCES[k]), "bytes": len(b), "sha256": sha(b)} for k,b in blobs.items()}
    docs = {k: doc(blobs[k]) for k in ('article','main','supplement')}
    normalized = {k: '\n'.join(v['paragraphs']).replace('−','-') for k,v in docs.items()}
    old, new = csv_rows(blobs['saved_4905']), csv_rows(blobs['saved_1900'])
    ordinal = next(p for p in docs['article']['paragraphs'] if p.startswith('Three ordinations')).replace('−','-')
    number = r'-?(?:\d+(?:\.\d+)?|\.\d+)'
    metrics=[]
    for method, pattern in [('UMAP', rf'UMAP achieved a trustworthiness of ({number}) and a Spearman correlation of ({number})'),
                            ('t-SNE',rf't-SNE reached ({number}) and ({number})'),
                            ('PCoA',rf'PCoA reached ({number}) and ({number})')]:
        m=re.search(pattern,ordinal)
        metrics.extend((method,k,v) for k,v in zip(('trustworthiness','distance_spearman'),m.groups()))
    m=re.search(rf'({number}) on the original distances, ({number}) for UMAP, ({number}) for t-SNE and ({number}) for PCoA',ordinal)
    metrics.extend((method,'silhouette_by_zone',value) for method,value in zip(('original distances','UMAP','t-SNE','PCoA'),m.groups()))
    comparisons=[{'method':method,'metric':metric,'article_literal':literal,
                  'saved_1900':float(new[method][metric]),'saved_4905':float(old[method][metric]),
                  'matches_1900':match(literal,new[method][metric]),'matches_4905':match(literal,old[method][metric])}
                 for method,metric,literal in metrics]
    discussion=next(p for p in docs['article']['paragraphs'] if p.startswith('The three structure analyses')).replace('−','-')
    silhouettes=re.search(rf'UMAP ({number}), t-SNE ({number}), PCoA ({number}), original distances ({number})',discussion)
    discussion_checks=[{'method':method,'literal':literal,'matches_1900':match(literal,new[method]['silhouette_by_zone'])}
                       for method,literal in zip(('UMAP','t-SNE','PCoA','original distances'),silhouettes.groups())]
    facts=blobs['facts'].decode().replace('**','').replace('−','-')
    fact_checks=[]
    for line in facts.splitlines():
        cells=[c.strip() for c in line.strip().strip('|').split('|')]
        if len(cells)==4 and cells[0] in new:
            for key,value in zip(('trustworthiness','distance_spearman','silhouette_by_zone'),cells[1:]):
                if value=='-':
                    continue
                fact_checks.append({'method':cells[0],'metric':key,'literal':value,'matches_1900':match(value,new[cells[0]][key])})
    captions={kind:[re.match(rf'^{kind}\s+(S\d+[a-z]?)\.',p)[1]
                    for p in docs['supplement']['paragraphs'] if re.match(rf'^{kind}\s+(S\d+[a-z]?)\.',p)]
              for kind in ('Table','Figure')}
    stale_captions=[p for p in docs['supplement']['paragraphs']
                    if re.match(r'^Table S(?:10|13|24|28)\.',p)
                    and any(s in p for s in ('numbered after','is lettered'))]
    notes=blobs['notes'].decode().replace('**','')
    readme=blobs['readme'].decode()
    previous=json.loads((ROOT/'verification_review_round4/review_manifest.json').read_text())
    prior_map={x['path']:x['sha256'] for x in previous['current_source_and_baseline_artifact_identities']}
    tracked=git('ls-files','-z').decode().rstrip('\0').split('\0')
    commits=git('log','--format=%H%x09%aI%x09%s').decode().splitlines()
    baseline='3f0130dd'  # resolved below; no reliance on an unverified abbreviated suffix
    baseline=git('rev-parse','3f0130d').decode().strip()
    head=git('rev-parse','HEAD').decode().strip()
    baseline_paths=git('ls-tree','-r','--name-only',baseline).decode().splitlines()
    baseline_checks=[]
    for relative in ('Pf8_Ghana_manuscript_REVISED.docx','Pf8_Ghana_manuscript_REVISED.pdf',
                     'article/Additional_file_1.docx','article/Additional_file_1.pdf',
                     'article/Pf8_Ghana_article.docx','article/Pf8_Ghana_article.pdf',
                     'article/article.md','article/CANONICAL_FACTS_FOR_ARTICLE.md',
                     'corrected/dimred_comparison_analysisset.csv','provenance_final/audit_scripts/README.md'):
        digest=sha(git('show',f'{baseline}:{relative}'))
        expected=prior_map[str(ROOT/relative)]
        baseline_checks.append({'path':relative,'git_baseline_sha256':digest,'last_review_sha256':expected,'matches':digest==expected})
    inventory=json.loads((OUT/'change_inventory.json').read_text())
    scientific=[r for r in inventory['files'] if any(s in r['path'] for s in
                ('/provenance_final/scripts/','/provenance_final/audit_logs/','/verification_audit/'))]
    checks={
      'all_ten_article_metrics_now_match_saved_1900_values':len(comparisons)==10 and all(c['matches_1900'] for c in comparisons),
      'no_article_metric_matches_old_4905_values':not any(c['matches_4905'] for c in comparisons),
      'all_four_discussion_silhouettes_match_saved_1900':len(discussion_checks)==4 and all(c['matches_1900'] for c in discussion_checks),
      'canonical_facts_metrics_match_saved_1900':len(fact_checks)==11 and all(c['matches_1900'] for c in fact_checks),
      'n1900_alias_is_byte_identical_to_saved_corrected_csv':blobs['n1900_alias']==blobs['saved_1900'],
      'n4905_alias_is_byte_identical_to_saved_legacy_csv':blobs['n4905_alias']==blobs['saved_4905'],
      'misleading_analysisset_alias_removed':not (ROOT/'corrected/dimred_comparison_analysisset.csv').exists(),
      'article_figure_still_matches_corrected_1900_image':sum(m['sha256']==inputs['figure']['sha256'] for m in docs['article']['media'])==1,
      'article_supplementary_ranges_corrected': 'Figure S1–S23 and Table S1–S52' in normalized['article'],
      'supplement_captions_still_unique_sequential_52_tables_23_figures': captions['Table']==[f'S{i}' for i in range(1,53)] and captions['Figure']==[f'S{i}' for i in range(1,24)],
      'domain_partition_and_mixed_scope_propagated_to_both_long_docs':all('16 are genuinely anchored outside the panel and three' in normalized[k]
           and '58 fall at records the reconstruction actually selects' in normalized[k]
           and 'remaining four fall at genuinely off-anchor records' in normalized[k] for k in ('main','supplement')),
      'domain_zero_effect_conclusion_qualified_in_both_long_docs':all('no published number that this evidence reaches' in normalized[k] for k in ('main','supplement')),
      'readme_inventory_domain_partition_corrected':'16 genuinely off-anchor, three anchored at panel positions' in readme,
      'one_vs_both_zone_pair_inconsistency_removed':all('both zone pairs that share a study' in normalized[k] and 'the one zone pair that shares' not in normalized[k] for k in ('main','supplement')),
      'FDR_count_sentence_conditional_in_both_long_docs':all('Counts with Benjamini–Hochberg q-values against the pseudo-observed null, conditional on that null being adequately calibrated' in normalized[k] for k in ('main','supplement')),
      'two_directions_claim_replaced_with_conditional_edge_statement':all('not identified directions of historical exchange' in normalized[k] and 'two directions of exchange are statistically supported' not in normalized[k] for k in ('main','supplement')),
      'free_gene_flow_ending_replaced_with_unmeasured_connectivity_statement':all('does not quantify contemporary connectivity' in normalized[k] and 'on top of free gene flow' not in normalized[k] for k in ('main','supplement')),
      'section_574_conservative_threshold_scope_corrected':all('does not establish the direction of the error for the final 3,916-SNP run' in normalized[k] for k in ('main','supplement')),
      'section_56_still_claims_final_threshold_conservative':all('because proper matching lowers the threshold, the reported threshold is the conservative one' in normalized[k] for k in ('main','supplement')),
      'strict_bifurcating_tree_conclusion_still_unqualified':all('What the graph establishes is that a strictly bifurcating tree does not describe these populations' in normalized[k] for k in ('main','supplement')),
      'four_obsolete_caption_explanations_remain':len(stale_captions)==4,
      'verification_notes_unchanged_from_last_review':inputs['notes']['sha256']==prior_map[str(ROOT/SOURCES['notes'])],
      'older_notes_still_call_cancellation_underflow':'same subtraction underflows to exactly zero' in notes,
      'older_notes_read_level_and_independent_X_claims_remain':'confirmed genuine at read level' in notes and 'confirming independently that no spanning deletion' in notes,
      'notes_later_numerical_caveat_retained':'remaining three are moderate p-values' in notes and 'does not identify a particular build' in notes,
      'authors_funding_contributions_citation_repository_placeholders_remain':all(s in normalized['article'] for s in ('AUTHOR NAMES AND AFFILIATIONS TO BE SUPPLIED','FUNDING STATEMENT TO BE SUPPLIED','AUTHOR CONTRIBUTIONS TO BE SUPPLIED','CITATION TO BE SUPPLIED: WHO World Malaria Report','REPOSITORY DOI TO BE SUPPLIED')),
      'known_scientific_audit_logs_and_lean_files_unchanged':bool(scientific) and not any(r['changed'] for r in scientific),
      'git_baseline_has_8084_files_current_has_8086':len(baseline_paths)==8084 and len(tracked)==8086,
      'git_contains_baseline_plus_one_correction_commit':len(commits)==2 and head.startswith('e590ba7') and baseline.startswith('3f0130d'),
      'git_baseline_matches_ten_prior_reviewed_source_identities':len(baseline_checks)==10 and all(c['matches'] for c in baseline_checks),
      'claimed_analysis_cohort_log_not_among_tracked_files':not any(Path(p).name=='step03_qcset.log' for p in tracked),
    }
    validation={'generated_utc':datetime.now(timezone.utc).isoformat(),'checker':str(Path(__file__).resolve()),
      'checker_sha256':sha(Path(__file__).read_bytes()),'runtime':sys.executable,'input_identities':inputs,
      'assertion_meaning':'Passing confirms the stated fix or remaining finding; not statistical or provenance certification.',
      'assertions':checks,'ordination':{'article_paragraph':ordinal,'metrics':comparisons,'discussion_silhouettes':discussion_checks,'canonical_facts':fact_checks},
      'supplementary_numbering':{'captions':captions,'obsolete_caption_explanations':stale_captions},
      'git':{'baseline':baseline,'head':head,'commits':commits,'baseline_file_count':len(baseline_paths),'current_file_count':len(tracked),
             'baseline_identity_checks':baseline_checks,'claimed_analysis_log_tracked':False},
      'scope_limits':['Saved output identities and printed metrics were checked; no dimensionality-reduction inference was rerun.',
                      'The quoted 1900-matrix log and suffix-patched generating script were not newly archived locally.',
                      'Git captures current snapshots and edits; it does not authenticate pre-existing run lineage.',
                      'Scientific pipeline and remote audit scripts were not executed; no new Lean build or implementation proof.']}
    (OUT/'revision_validation.json').write_text(json.dumps(validation,indent=2,ensure_ascii=False)+'\n')
    print(json.dumps({'passed':sum(checks.values()),'total':len(checks),'failed':[k for k,v in checks.items() if not v]}))
    return 0 if all(checks.values()) else 1


if __name__=='__main__':
    raise SystemExit(main())
