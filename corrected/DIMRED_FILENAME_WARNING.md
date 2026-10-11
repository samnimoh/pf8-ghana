# Warning: the upstream dimred filenames are inverted

On the analysis server:

| Server file | Cohort it actually describes | Log that produced it |
|---|---|---|
| `results/dimred_comparison.csv` | **4,905** release-QC-pass isolates | `logs/step03_dimred.log` — "Ghana submatrix (4905, 4905)" |
| `results/dimred_comparison_qcset.csv` | **1,900** analysis isolates | `logs/step03_qcset.log` — "Ghana submatrix (1900, 1900) built for this subset" |

The `_qcset` suffix therefore names the **analysis** set, and the unsuffixed file names the
**QC-pass** set — the opposite of what both names suggest.

The trap is worse than the naming. `step03_umap.py` was patched to take a `--suffix`, but the
patch suffixed the file *writes* and not the `print` statements, so **both logs end with
`Scores -> .../results/dimred_comparison.csv`**. The 1,900-isolate run reports that it wrote the
unsuffixed file; it did not. Anyone who reads the log line instead of checking the file will pick
up the 4,905-isolate numbers believing them to be the 1,900-isolate ones. That is exactly what
happened in this project, and the error reached the article.

Unambiguous local copies, named for their cohort and verified by the submatrix shape in the
generating log, are kept alongside this note:

- `dimred_comparison_n1900_analysisset.csv`
- `dimred_comparison_n4905_qcpassset.csv`

Use those. Do not use a filename or a log line as evidence of cohort; use the submatrix shape.
