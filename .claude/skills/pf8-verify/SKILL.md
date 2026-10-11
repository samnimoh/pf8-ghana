---
name: pf8-verify
description: Verify a number, claim or provenance question in the Pf8 Ghana analysis against the canonical facts and the saved outputs. Use before asserting any figure, and whenever a review or collaborator disputes one.
---

# Verifying a claim

Never settle a numeric question by reading it back from the prose that contains it.

## 1. Is it in the canonical facts?

```bash
grep -n -i "<the number or marker>" article/CANONICAL_FACTS_FOR_ARTICLE.md
```

That file is the single source of truth for the article. If the number is not there and not in a
saved output, the answer is `[NUMBER NOT AVAILABLE]` — never reconstruct it.

## 2. Trace it to a saved output

`corrected/` holds the verified tables: `final_fst_pairwise.csv`, `sensitivity_summary.csv`,
`mantel_jackknife_region.csv`, `codon_panel_residues.csv`, `codon_panel_haplotypes.csv`,
`final_xtx_calibration.json`, `final_outlier_genes.csv`, `outlier_quality_check.csv`,
`dimred_comparison_n1900_analysisset.csv`, `dimred_comparison_n4905_qcpassset.csv`.

**md5 the local copy against the server before using it.** Stale local snapshots have produced
false findings four times.

## 3. Establish the cohort from construction

The decisive question is almost always *which isolates*. 1,900 is the analysis set; 4,905 is the
release-QC-pass set. Filenames here are actively misleading and logs misreport their output paths —
use the shape or denominator printed by the generating run.

## 4. Recompute

Cheap and decisive: denominators, percentages, Wilson intervals, BH q-values, normal tails,
chi-square expected cells. An independent recomputation beats a quotation. Run Python with `-I`.

## 5. Separate the value from its scope

- "47,012 of 47,012 agree" — *across the 25 of 57 codons MalariaGEN publishes per sample*.
- "no WHO-screened *pfk13* allele" — *among called isolates, 2009–2021*; 22 of 23 codons are fixed
  and codon 458 is at 0.9995.
- "20.6%" — an *expected-null-exceedance ratio*, not a measured false-discovery rate.

## 6. Answer

**CONFIRMED / CORRECTED / UNVERIFIABLE**, with the value, the file it came from, how you established
the cohort, and the correct value if it changed. Then check whether the same claim appears elsewhere
in another phrasing — it usually does.

For anything broader than a single number, delegate to the `pf8-verifier` subagent.
