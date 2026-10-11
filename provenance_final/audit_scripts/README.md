# Empirical audit scripts and logs

Each script is read-only against the MalariaGEN Pf8 Zarr store
(`https://pf8-release.cog.sanger.ac.uk/zarr`) and the project's own saved outputs. None
writes to the pipeline. They were run on host `bacg2` with
`/home/gyadu/.conda/envs/spatial/bin/python`; the captured stdout is in `../audit_logs/`.

| Script | Log | Claim it supports |
|---|---|---|
| `check_n458d.py` | `n458d.log` | The single *pfk13* Asn458Asp call. Retrieves GT/AD/DP/GQ at the three codon-458 positions for all 1,900 isolates. Result: PF0106-C homozygous for ALT2 `C` at Pf3D7_13_v3:1,725,626, `AD = [0,0,40]`, `DP = 40`, `GQ = 99`, at a FILTER_PASS site with numalt 2. |
| `check_panel_filter.py` | `panel_filter.log` | Whether any reported residue depends on a record failing the Pf8 release filter. Result: 29 non-PASS records at panel positions; 6 non-reference calls from them, at *pfk13* codons 675, 561, 553. |
| `check_codons.py` | `codons.log` | What those non-PASS alternatives would encode, reconstructed from the reference FASTA rather than inferred from marker names. Result: codons 561 and 553 synonymous; codon 675 gives Pro, not the validated Val. |
| `check_domain.py` | `domain.log` | step12's supported input domain over all 171 panel positions. Result: 125 records at panel positions, 16 with a length-changing ALT, 2 multi-base REF, 19 off-anchor spanning records, 0 record-free codons; genotypes fetched for all 32 affected records. |
| `check_alleles.py` | `alleles.log` | Per-ALT-index homozygous carrier counts at the two records carrying both supported and unsupported alleles. Result: all carriers on supported equal-length alleles; zero on any length-changing allele. |
| *(carrier detail)* | `validated_marker_carriers.log` | Genotypes, AD, DP and GQ for the six carriers at the three non-PASS *pfk13* marker codons. |

## What these do and do not establish

They establish what is in the Pf8 release store at the named coordinates, and what the
analysis isolates carry there. The genotype data come from the public store, so the queries are
reproducible in principle — but these scripts are **not portable as written**: they hard-code server
paths to `analysis_samples.csv`, `sample_qc_full.csv`, `codon_panel_residues.csv` and the 3D7
reference FASTA, and they pin no dependency versions. Re-running them elsewhere requires supplying
those inputs and an environment with `numpy`, `pandas`, `requests` and `numcodecs`.

They do **not** establish that the archived `codon_panel_residues.csv` was produced by the
archived `step12_codon_panel.py` on the archived inputs — that is a separate provenance
question, and the exact final command and executable revision are still not archived. They
also do not constitute an independent read-alignment examination: `AD`, `DP` and `GQ` are
MalariaGEN's own called fields, not a reanalysis of the underlying reads.
