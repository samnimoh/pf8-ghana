# Pf8 Ghana — project instructions

Doctoral analysis: **population structure and antimalarial resistance markers in
*Plasmodium falciparum* across Ghana's agro-ecological zones**, using MalariaGEN Pf8.

Read this before touching anything. Most of it is scar tissue from real errors.

---

## 1. The server

```bash
ssh gyadu            # 192.168.0.152, user gyadu, key ~/.ssh/id_ed25519_gyadu
```

Key-based login works; **no password is ever needed and you must never type or ask for one.**

| Thing | Value |
|---|---|
| Hostname | `bacg2` |
| Project root | `/media/biodataA/pf8/gyadu/` |
| Python | `/home/gyadu/.conda/envs/spatial/bin/python` (3.10) — **not** on `PATH`; call the full path |
| Conda env | `spatial` (there is no `conda` on the non-login `PATH`; do not try `conda activate`) |
| Layout | `scripts/ data/ interim/ results/ figures/ logs/` |
| Disk | ~447 GB free of 7.6 TB — **tight. Do not write large intermediates.** |
| Pf8 Zarr | `https://pf8-release.cog.sanger.ac.uk/zarr` (public, reachable from the server) |

Scratch work goes in the server's `/tmp`. **Never modify anything under
`/media/biodataA/pf8/gyadu/` that is not part of this pipeline**, and prefer read-only queries.

Long server jobs: launch with `nohup ... > /tmp/x.log 2>&1 &` and poll the log. Do **not** write
shell `until` wait-loops against a workflow journal — see §5.

---

## 2. Rules that exist because they were broken

**Never take a cohort, a date or a provenance from a filename or a log line. Take it from the data.**
The canonical example: `results/dimred_comparison.csv` holds the **4,905**-isolate run and
`results/dimred_comparison_qcset.csv` holds the **1,900**-isolate run — the names are inverted —
and because a `--suffix` patch suffixed file *writes* but not `print` statements, **both logs end
`Scores -> results/dimred_comparison.csv`**. Cohort was settled only by the submatrix shape printed
in each log: `(4905, 4905)` vs `(1900, 1900)`. See `corrected/DIMRED_FILENAME_WARNING.md`.

**Refresh local copies before any numeric comparison.** Local snapshots have gone stale repeatedly
and produced false "defect found" reports. Compare md5s against the server.

**A tidy explanation of a mismatch is a red flag, not a resolution.** An agent once invented a
plausible reconciliation for a stale number ("the other figure is the count at p < 0.10") that the
data flatly contradicted.

**Sweep by concept, never by phrase.** Correcting the named wording of a claim and leaving the same
claim worded differently has happened in every round. One sweep found 93 instances of nine defects
that an external reviewer had spotted ~12 of. Check table cells, figure captions, status columns and
one-line Q&A rows specifically — that is where withdrawn claims survive.

**After fixing a claim, re-read every correction record that mentions the fix.** A note once said
wording "has been removed from Sections 5.6, 6.8 and 8.1" when §6.8 still carried it in other words.
A false correction record is worse than the original error: it tells the reader not to look.

**Assert occurrence counts on every text substitution** and write the file only at the end, so an
abort leaves it untouched. Editing `word/document.xml` directly: flattened-text greps both miss
strings split across runs and invent strings that are not contiguous. See
`[[docx-xml-editing-pitfalls]]` in memory.

**Never name a scratch file after a stdlib module** (`enum.py`, `re.py`, `types.py`). Run Python with
`-I`. This has broken unrelated tooling twice.

---

## 3. Claims that are forbidden

These were each asserted, refuted and withdrawn. Do not reintroduce them in any document.

- Panmixia, random mating, or differentiation described as absent/undetectable.
  Max pairwise *F*<sub>ST</sub> is 0.00232 and **five of six 95% CIs exclude zero**.
- Low *F*<sub>ST</sub> as an upper bound or ceiling on *true* differentiation.
- Isolation by distance as a supported result — it holds in 2 of 6 scenarios and 4 of 7 jackknife
  replicates and is reported as **not robust**.
- "Exactly two migration edges" or a settled TreeMix edge count. m = 2 is a **selected descriptive
  model**; the variance-explained rule prefers m = 3 over the full sweep, so the criteria disagree.
- "Empirical FDR" for 3.916/19 = 20.6% — it is an expected-null-exceedance ratio.
- MAF-matched pseudo-observed simulations — `pi.maf` truncates the simulated ancestral frequency.
- "All 23 *pfk13* codons fixed" — 22 are; codon 458 is at 0.9995 on one Asn458Asp call, which is
  **not** the validated N458Y.
- That holding zone constant isolates a technical/sequencing cause.
- End-to-end reproducibility from the archived snapshots.

**Single source of truth for numbers:** `article/CANONICAL_FACTS_FOR_ARTICLE.md`. Anything not in it
is written `[NUMBER NOT AVAILABLE]`, never invented.

---

## 4. Local layout and versioning

| Path | What |
|---|---|
| `article/Pf8_Ghana_article.docx` | the ~18pp Malaria Journal article |
| `article/Additional_file_1.docx` | the 198pp analysis record (Figure S1–S23, Table S1–S52) |
| `article/article.md` | **article source** — edit this, then rebuild |
| `article/CANONICAL_FACTS_FOR_ARTICLE.md` | the only permitted numbers |
| `Pf8_Ghana_manuscript_REVISED.docx` | 197pp working record; the supplement is generated from it |
| `corrected/` | verified output tables |
| `provenance_final/` | server scripts, audit scripts + logs, verification notes |

**This directory is a git repository.** Commit after every logical correction, with the reasoning in
the message. Never overwrite a deliverable without committing the prior state first — four of this
project's errors were stale or mislabelled files, and git is the remedy.

Regenerate **all** PDFs whenever any source changes; a stale PDF alongside a fresh DOCX has been
flagged by review.

---

## 5. Working style

- Verify before agreeing *and* before disagreeing. Across four review rounds the external reviewer
  was right on every substantive finding, and twice a correct finding was wrongly dismissed here.
- Use subagents and workflows for breadth; parallelise. The adversarial verify pass earns its cost —
  it has caught invented numbers, misattributed citations and forbidden-claim relapses.
- Send figures and rendered pages as proof of work as they appear.
- Ask interactively when there is more than one good option, rather than guessing in prose.
