#!/usr/bin/env python3
"""
STEP 9 — Functional annotation: outlier coordinates to gene identifiers.

The GFF is filtered to gene-level features before intersection, which keeps the
output from filling with exon and CDS rows for the same locus. Contig naming is
checked between the BED and the GFF first, because a silent mismatch there
produces an empty intersection that looks exactly like a clean null result.

Recovering pfcrt or pfdhfr is a positive control, not a finding. What sits
alongside them is the interesting part.

Usage:
    python step09_annotate.py
    python step09_annotate.py --flank 2000      # capture nearby regulatory hits
    python step09_annotate.py --feature gene
"""

from __future__ import annotations

import argparse
import gzip
import re
import subprocess
import shutil

import pandas as pd

import config as C


def open_gff(path):
    """PlasmoDB serves some releases gzipped; handle both without fuss."""
    path = str(path)
    if path.endswith(".gz"):
        return gzip.open(path, "rt")
    return open(path)

ATTR_RE = re.compile(r"(?:^|;)\s*(ID|Name|description|gene_product)\s*=\s*([^;]+)")

ANTIGENIC_FAMILIES = {
    "var": r"\b(?:var|PfEMP1|erythrocyte membrane protein 1)\b",
    "rifin": r"\brifin\b",
    "stevor": r"\bstevor\b",
    "surfin": r"\bsurfin\b",
    "msp": r"\bmerozoite surface protein\b",
    "ama1": r"\bapical membrane antigen\b",
    "csp": r"\bcircumsporozoite\b",
    "trap": r"\bthrombospondin-related anonymous protein\b",
    "eba": r"\berythrocyte binding antigen\b",
    "rh": r"\breticulocyte binding protein homolog(?:ue)?\b",
}

# Subset of the above that sits in subtelomeric, hard-to-genotype territory.
LOW_CONFIDENCE_FAMILIES = ("var", "rifin", "stevor", "surfin")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--flank", type=int, default=0,
                   help="Extend each outlier position by N bp on both sides.")
    p.add_argument("--feature", default="gene",
                   help="GFF feature type to intersect against (substring match).")
    return p.parse_args()


def parse_attrs(attr: str) -> dict[str, str]:
    out = {}
    for key, val in ATTR_RE.findall(attr):
        out[key] = val.strip()
    return out


def main() -> None:
    args = parse_args()
    C.banner("STEP 9 — functional annotation via PlasmoDB")

    if shutil.which("bedtools") is None:
        raise RuntimeError("bedtools not on PATH. conda activate pf8ghana")

    bed = C.require(C.BAYPASS_DIR / "outlier_snps.bed",
                    "Run step08c_calibrate_xtx.py first.")
    gff = C.require(C.PLASMODB_GFF,
                    "Place the PlasmoDB 3D7 GFF in data/. Filename in config.py.")

    bed_df = pd.read_csv(bed, sep="\t", header=None,
                         names=["chrom", "start", "end", "xtx"])
    print(f"Outlier SNPs: {len(bed_df):,}")
    if bed_df.empty:
        print("No outliers to annotate. Revisit the Step 8c threshold.")
        return

    # ---- contig naming sanity check --------------------------------------
    gff_contigs = set()
    with open_gff(gff) as fh:
        for line in fh:
            if line.startswith("#"):
                continue
            gff_contigs.add(line.split("\t", 1)[0])
            if len(gff_contigs) > 40:
                break
    bed_contigs = set(bed_df["chrom"].astype(str))
    overlap = bed_contigs & gff_contigs
    print(f"Contig names shared between BED and GFF: {len(overlap)}")
    if not overlap:
        raise ValueError(
            "No contig names in common.\n"
            f"  BED examples: {sorted(bed_contigs)[:3]}\n"
            f"  GFF examples: {sorted(gff_contigs)[:3]}\n"
            "Rename one side before intersecting — an empty result here is "
            "indistinguishable from a genuine null."
        )

    # ---- prepare inputs ---------------------------------------------------
    work_bed = C.INTERIM_DIR / "outlier_snps_padded.bed"
    padded = bed_df.copy()
    if args.flank:
        padded["start"] = (padded["start"] - args.flank).clip(lower=0)
        padded["end"] = padded["end"] + args.flank
        print(f"Applied {args.flank} bp flanks.")
    padded.sort_values(["chrom", "start"]).to_csv(
        work_bed, sep="\t", header=False, index=False)

    genes_gff = C.INTERIM_DIR / "plasmodb_genes.gff"
    kept = 0
    with open_gff(gff) as src, open(genes_gff, "w") as dst:
        for line in src:
            if line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) > 2 and args.feature in parts[2]:
                dst.write(line)
                kept += 1
    print(f"GFF features matching '{args.feature}': {kept:,} -> {genes_gff.name}")

    # ---- intersect --------------------------------------------------------
    cmd = ["bedtools", "intersect", "-a", str(work_bed), "-b", str(genes_gff),
           "-wa", "-wb"]
    print("\n$ " + " ".join(cmd))
    with open(C.ANNOTATED_OUTLIERS, "w") as out:
        res = subprocess.run(cmd, stdout=out, stderr=subprocess.PIPE, text=True)
    if res.returncode != 0:
        raise RuntimeError(f"bedtools failed:\n{res.stderr}")

    cols = ["snp_chrom", "snp_start", "snp_end", "xtx",
            "g_chrom", "g_source", "g_type", "g_start", "g_end",
            "g_score", "g_strand", "g_phase", "g_attrs"]
    try:
        ann = pd.read_csv(C.ANNOTATED_OUTLIERS, sep="\t", header=None, names=cols)
    except pd.errors.EmptyDataError:
        print("\nNo outlier fell inside a gene feature.")
        print("Intergenic enrichment is plausible in Pf, but check --flank and")
        print("the feature type before concluding anything.")
        return

    attrs = ann["g_attrs"].apply(parse_attrs)
    ann["gene_id"] = attrs.apply(lambda d: d.get("ID", "")).str.replace(
        r"^gene[:_-]?", "", regex=True)
    ann["gene_name"] = attrs.apply(lambda d: d.get("Name", ""))
    ann["product"] = attrs.apply(
        lambda d: d.get("description", d.get("gene_product", "")))

    C.banner("Annotated outliers")
    per_gene = (ann.groupby(["gene_id", "gene_name", "product"], dropna=False)
                   .agg(n_outlier_snps=("xtx", "size"), max_xtx=("xtx", "max"))
                   .reset_index()
                   .sort_values("max_xtx", ascending=False))

    print(f"{len(ann):,} SNP-gene overlaps across {len(per_gene):,} genes\n")
    print("Top 25 genes by maximum XtX:")
    show = per_gene.head(25).copy()
    show["product"] = show["product"].astype(str).str.slice(0, 48)
    print(show.to_string(index=False))

    # ---- known resistance loci -------------------------------------------
    C.banner("Known antimalarial resistance loci")
    found = per_gene[per_gene["gene_id"].isin(C.KNOWN_RESISTANCE_LOCI)]
    if len(found):
        for _, r in found.iterrows():
            label = C.KNOWN_RESISTANCE_LOCI[r["gene_id"]]
            print(f"  {label:<12} {r['gene_id']}  "
                  f"{int(r['n_outlier_snps'])} SNPs, max XtX {r['max_xtx']:.1f}")
    else:
        print("  None recovered.")
        print("  Absence is informative but ambiguous: it may reflect genuinely")
        print("  weak recent selection, or simply insufficient power at this")
        print("  sample size and zone count.")
    missed = [f"{v} ({k})" for k, v in C.KNOWN_RESISTANCE_LOCI.items()
              if k not in set(per_gene["gene_id"])]
    if missed:
        print(f"\n  Not in the outlier set: {', '.join(missed)}")

    # ---- antigenic variation gene families -------------------------------
    C.banner("Antigenic variation and invasion gene families")
    text = (per_gene["product"].astype(str) + " "
            + per_gene["gene_name"].astype(str))
    family_hits = {}
    per_gene["family"] = ""
    for fam, pattern in ANTIGENIC_FAMILIES.items():
        m = text.str.contains(pattern, case=False, regex=True, na=False)
        if m.any():
            family_hits[fam] = int(m.sum())
            per_gene.loc[m & (per_gene["family"] == ""), "family"] = fam

    if family_hits:
        for fam, count in sorted(family_hits.items(), key=lambda kv: -kv[1]):
            flag = "  (low-confidence region)" if fam in LOW_CONFIDENCE_FAMILIES else ""
            print(f"  {fam:<8} {count:>4} outlier genes{flag}")
        print("\nTop antigenic hits by XtX:")
        print(per_gene[per_gene["family"] != ""]
              .sort_values("max_xtx", ascending=False)
              [["gene_id", "gene_name", "family", "n_outlier_snps", "max_xtx"]]
              .head(15).to_string(index=False))
    else:
        print("  No outlier fell in a recognised antigenic or invasion family.")

    per_gene.to_csv(C.RESULTS_DIR / "outlier_genes.csv", index=False)

    # ---- call-quality caution --------------------------------------------
    low_conf = per_gene["family"].isin(LOW_CONFIDENCE_FAMILIES)
    n_hv = int(low_conf.sum())
    if n_hv:
        C.banner("Call-quality caution")
        print(f"{n_hv} of those sit in subtelomeric multigene families.")
        print("Immune-driven diversifying selection on var and rifin is real")
        print("biology, and short-read genotyping in those regions is also")
        print("genuinely unreliable — the two produce the same signature here.")
        print("Separating them needs depth, mappability and allele-balance")
        print("evidence per locus, not the outlier statistic alone. Treat these")
        print("as candidates requiring manual inspection, not as findings.")
        print(per_gene.loc[low_conf, ["gene_id", "gene_name", "family", "max_xtx"]]
              .sort_values("max_xtx", ascending=False).head(15).to_string(index=False))

    print(f"\nRaw intersection -> {C.ANNOTATED_OUTLIERS}")
    print(f"Gene summary     -> {C.RESULTS_DIR / 'outlier_genes.csv'}")


if __name__ == "__main__":
    main()
