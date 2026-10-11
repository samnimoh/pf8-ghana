"""Check delivered packages, reviewer identities, and the bounded tracked change set."""
import hashlib
import io
import json
from pathlib import Path
import runpy
import subprocess
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
BASELINE = '64515dc'
GIT = runpy.run_path(str(ROOT / 'tools/git_runtime.py'))['resolve_git']()

def sha(data):
    return hashlib.sha256(data).hexdigest()

def main():
    checks = {}
    review = json.loads((OUT / 'final_document_followup_review.json').read_text())
    checks['independent_document_checks_pass'] = review['status'] in {'pass', 'bounded_pass'} and not review['findings'] and all(c['pass'] for c in review['checks'])
    checks['reviewed_source_identities_still_match'] = all(sha((ROOT / name).read_bytes()) == digest for name, digest in review['source_sha256'].items())
    paths = ['Pf8_Ghana_manuscript_REVISED.docx', 'article/Additional_file_1.docx', 'article/Pf8_Ghana_article.docx']
    package_details = []
    for name in paths:
        old_bytes = subprocess.check_output([GIT, '-C', str(ROOT), 'show', BASELINE + ':' + name])
        with zipfile.ZipFile(io.BytesIO(old_bytes)) as old, zipfile.ZipFile(ROOT / name) as new:
            checks[name + ': archive_crc'] = new.testzip() is None
            checks[name + ': unique_package_parts'] = len(new.namelist()) == len(set(new.namelist()))
            for part in new.namelist():
                if part.endswith(('.xml', '.rels')):
                    ET.fromstring(new.read(part))
            checks[name + ': all_xml_parses'] = True
            media_old = {p: sha(old.read(p)) for p in old.namelist() if p.startswith('word/media/') and not p.endswith('/')}
            media_new = {p: sha(new.read(p)) for p in new.namelist() if p.startswith('word/media/') and not p.endswith('/')}
            checks[name + ': all_figure_bytes_unchanged'] = media_old == media_new
            package_details.append({'path': name, 'sha256': sha((ROOT/name).read_bytes()), 'media_parts': len(media_new)})
    facts = 'article/CANONICAL_FACTS_FOR_ARTICLE.md'
    checks['canonical_facts_unchanged'] = (ROOT/facts).read_bytes() == subprocess.check_output([GIT, '-C', str(ROOT), 'show', BASELINE + ':' + facts])
    notes = 'provenance_final/VERIFICATION_NOTES.md'
    original_notes = subprocess.check_output([GIT, '-C', str(ROOT), 'show', BASELINE + ':' + notes])
    checks['earlier_verification_notes_preserved_as_prefix'] = (ROOT/notes).read_bytes().startswith(original_notes)
    allowed = set(paths + [p.replace('.docx', '.pdf') for p in paths] + ['article/article.md', 'tools/build_article.py', 'tools/make_supplement.py', 'tools/README.md', 'tools/git_runtime.py', notes])
    hygiene = json.loads((ROOT/'verification_review_round7/independent_tool_hygiene_review.json').read_text())
    utilities = next(c for c in hygiene['conclusions'] if c['id'] == 'nine_git_literals')['scripts']
    allowed.update(str(Path(p['path']).relative_to(ROOT)) for p in utilities)
    changes = subprocess.check_output([GIT, '-C', str(ROOT), 'diff', '--name-status', '--no-renames', BASELINE, '--'], text=True).splitlines()
    changed = []
    for line in changes:
        change, path = line.split('\t', 1)
        changed.append(path)
        # These newly added, local review artifacts are the evidence for this
        # correction. Do not exempt modifications to any earlier review record.
        if change == 'A' and path.startswith(('verification_fixes_round7/', 'verification_review_round7/')) and Path(path).suffix in {'.py', '.json', '.md'}:
            allowed.add(path)
    checks['no_tracked_scientific_data_scripts_or_proofs_changed'] = set(changed) <= allowed
    result = {'status': 'bounded_pass' if all(checks.values()) else 'failed', 'checks': checks,
        'packages': package_details, 'changed_tracked_files': changed,
        'scope': 'Document package integrity, unchanged figure bytes and canonical facts, exact reviewer identity, and bounded tracked changes. No scientific recalculation or Python-to-Lean proof claim.'}
    (OUT/'document_validation.json').write_text(json.dumps(result, indent=2) + '\n')
    if not all(checks.values()):
        raise ValueError([name for name, ok in checks.items() if not ok])
    print(f'{len(checks)} package/protection checks passed; independent document review has {len(review["checks"])} passing checks.')

if __name__ == '__main__':
    main()
