#!/usr/bin/env python3
"""Seal read-only review evidence and confirm no reviewed source drift."""
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import runpy

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
# Anchor shared helper discovery to this script so Python -I works from any cwd.
GIT = runpy.run_path(str(ROOT / 'tools' / 'git_runtime.py'))['resolve_git']()
HEAD = 'd59bbf6722c36b8f8f09e707a2290fbb699ed83f'


def identity(p):
    if not p.exists():
        return {'path': str(p), 'bytes': None, 'sha256': None}
    data = p.read_bytes()
    return {'path': str(p), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()}


def git(*args):
    return subprocess.check_output([GIT, *args], cwd=ROOT).decode()


def main():
    inventory = json.loads((OUT / 'change_inventory.json').read_text())
    checks = json.loads((OUT / 'revision_validation.json').read_text())
    tools = json.loads((OUT / 'independent_tool_review.json').read_text())
    render = json.loads((OUT / 'render_review.json').read_text())
    sources = {r['path']: {k: r.get(k) for k in ('path', 'bytes', 'sha256')}
               for r in inventory['files'] + inventory['new_source_files']}
    baseline = identity(Path(inventory['baseline_review_manifest']))
    sources[baseline['path']] = baseline
    drift = [p for p, expected in sources.items() if identity(Path(p))['sha256'] != expected['sha256']]
    helper_drift = [p for p, expected in tools['source_hashes_before'].items() if identity(Path(p))['sha256'] != expected]
    input_drift = [r['path'] for r in checks['input_identities'].values() if identity(Path(r['path']))['sha256'] != r['sha256']]
    render_drift = [r[k]['path'] for r in render['comparisons'] for k in ('docx', 'supplied_pdf', 'fresh_pdf')
                    if identity(Path(r[k]['path']))['sha256'] != r[k]['sha256']]
    assert not (drift or helper_drift or input_drift or render_drift), (drift, helper_drift, input_drift, render_drift)
    assert git('rev-parse', 'HEAD').strip() == HEAD
    assert git('diff', '--name-only', 'HEAD').strip() == ''
    assert all(checks['assertions'].values())
    assert all(r['all_page_texts_match'] for r in render['comparisons'])
    status = git('status', '--short').splitlines()
    assert status == ['?? verification_review_round6/'], status
    manifest = OUT / 'review_manifest.json'
    link_targets = []
    for target in re.findall(r'\]\((/[^)]+)\)', (OUT / 'REVIEW_LATEST_REVISION.md').read_text()):
        p = Path(re.sub(r':\d+$', '', target))
        assert p.exists() or p == manifest, str(p)
        link_targets.append(str(p))
    selected = {'article': [7, 15],
        'manuscript': [9, 60, 61, 79, 90, 99, 104, 109, 148, 165, 172, 177],
        'supplement': [2, 80, 100]}
    visual = [{'document': label, 'page': page, 'visually_inspected': True,
        **identity(Path('/private/tmp/pf8_review_round6_latest') / label / f'page-{page}.png')}
        for label, pages in selected.items() for page in pages]
    assert len(visual) == 17 and all(r['sha256'] for r in visual)
    artifacts = [identity(p) for p in sorted(OUT.rglob('*')) if p.is_file() and p != manifest and '__pycache__' not in p.parts]
    record = {'generated_utc': datetime.now(timezone.utc).isoformat(),
        'review_report': str(OUT / 'REVIEW_LATEST_REVISION.md'),
        'git_reviewed_head': HEAD,
        'comparison_commit': '1afaf4b',
        'git_history': git('log', '--format=%H%x09%aI%x09%s').splitlines(),
        'git_status_at_finalization': status,
        'tracked_files_unchanged_during_review': True,
        'baseline_review_manifest': inventory['baseline_review_manifest'],
        'baseline_review_manifest_identity': baseline,
        'known_round5_files_compared': inventory['known_files_compared'],
        'changes_since_round5': inventory['changed_files'],
        'new_source_files': inventory['new_source_files'],
        'current_source_and_baseline_artifact_identities': list(sources.values()),
        'artifact_hashes': artifacts,
        'source_drift': drift, 'helper_source_drift': helper_drift,
        'input_drift': input_drift, 'render_input_drift': render_drift,
        'targeted_assertions': {'passed': sum(checks['assertions'].values()), 'total': len(checks['assertions']), 'meaning': checks['assertion_meaning']},
        'helper_scratch_test_count': len(tools['results']),
        'server_readonly_checks': checks['server_output_checks'],
        'server_readonly_operation': 'Existing five output files were checked with md5sum over the established gyadu SSH connection; no remote scientific or audit script was executed.',
        'pdf_comparison': {'all_pages_checked': 413, 'counts': [18, 197, 198],
            'method': 'Complete page text comparison after whitespace and page-footer normalization',
            'all_page_layout_certified': False},
        'selected_visual_review': visual,
        'absolute_report_link_targets': link_targets,
        'scope_limits': ['No manuscript, scientific script, scientific output, or prior review was modified.',
            'No scientific pipeline or biological audit script was executed.',
            'Document helper tests used disposable synthetic inputs or copied Word packages.',
            'Matching output identities do not authenticate complete historical command/revision/input lineage.',
            'Existing Lean validation and proofs were unchanged; no new Lean build or implementation-refinement proof was performed.',
            'Temporary QA images are not deliverables; supplied permanent PDFs are the source for page references.'],
        'primary_reference_links': ['https://www.nature.com/articles/nrg2611',
            'https://journals.plos.org/plosgenetics/article?id=10.1371/journal.pgen.1002967']}
    manifest.write_text(json.dumps(record, indent=2, ensure_ascii=False) + '\n')
    assert all(Path(p).exists() for p in link_targets)
    print(json.dumps({'report': record['review_report'], 'source_identities': len(sources),
        'review_artifacts': len(artifacts), 'source_drift': drift,
        'targeted_assertions_passed': record['targeted_assertions']['passed'],
        'pdf_pages_compared': 413, 'selected_pages_visually_inspected': len(visual),
        'report_links_verified': len(link_targets)}))


if __name__ == '__main__':
    main()
