---
name: pf8-status
description: Orient on the Pf8 Ghana project from a cold start - check the server, the deliverables, git history and what is still open. Use this first when resuming work, on this machine or any other.
---

# Where this project stands

Run these, then summarise for the user. Takes under a minute.

## 1. Server reachable?

```bash
ssh -o ConnectTimeout=10 gyadu 'hostname; /home/gyadu/.conda/envs/spatial/bin/python -V; df -h /media/biodataA | tail -1'
```

If this fails, say so plainly and continue — most local work does not need the server.

## 2. Deliverables and whether the PDFs are stale

```bash
cd /Users/samnimoh/Desktop/chromo
ls -la article/*.docx article/*.pdf Pf8_Ghana_manuscript_REVISED.*
```

A PDF older than its DOCX is a defect — flag it and offer `/pf8-rebuild`.

## 3. Version history

```bash
git log --oneline | head -20
git status --short
```

Uncommitted changes mean someone stopped mid-correction. Read the diff before doing anything else.

## 4. Are the local outputs current?

```bash
for f in corrected/final_fst_pairwise.csv corrected/sensitivity_summary.csv corrected/mantel_jackknife_region.csv; do
  printf "%s  %s\n" "$(md5 -q "$f")" "$f"
done
ssh gyadu 'cd /media/biodataA/pf8/gyadu/results && md5sum fst_pairwise_final.csv sensitivity_summary.csv mantel_jackknife_region.csv 2>/dev/null'
```

Any mismatch: the local copy is stale. Refresh before comparing numbers against anything.

## 5. Open items

Read the end of `provenance_final/VERIFICATION_NOTES.md` and the most recent commit message.

Known to be outstanding unless the history says otherwise:
- author names, affiliations, funding and contributions in the article
- the Ghana burden citation (`[CITATION TO BE SUPPLIED]`) and the repository DOI
- the CERSGIS email for the agro-ecological layer's licence and accession
- depositing the code/data archive the data-availability statement points to
- exact final command revisions and raw BayPass POD inputs are not archived, so the pipeline is
  inspectable but not re-executable end to end

## Report

Give the user: server up or down, whether the deliverables are in sync, the last correction made,
and the open items. Do not start work until they choose a direction.
