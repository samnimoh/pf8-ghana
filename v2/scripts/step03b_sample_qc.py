#!/usr/bin/env python3
"""
STEP 3b — Sample-level quality control before anything downstream depends on it.

Four checks, in rough order of how much damage skipping them does.

Fws (within-host fixation index) measures how far a sample's read-level allele
frequencies sit from the population's. Low Fws means multiple genomes in one
infection. Ghana is a high-transmission setting where polyclonality is the norm,
and a mixed infection donates allele frequencies from several parasites to a
single genotype column. ADMIXTURE reads that as intermediate ancestry — so an
uncorrected run risks describing the transmission-intensity gradient across the
ecological zones rather than the ancestry structure you set out to estimate.

Clonal pruning removes near-identical isolates. Outbreak-linked or repeat-sampled
parasites inflate within-zone homogeneity, which inflates between-zone FST. The
Step 3 distance submatrix already holds everything needed to find them.

Call rate and heterozygosity outliers catch the samples that will contribute
mostly missing data or mostly noise.

Everything is written to a QC table with an explicit `qc_pass` column. Step 4a
reads that table when it exists and falls back to the Step 2 output when it does
not, so this step is optional in the mechanical sense and close to mandatory in
the scientific one.

Usage:
    python step03b_sample_qc.py
    python step03b_sample_qc.py --min-fws 0.95 --min-call-rate 0.8
    python step03b_sample_qc.py --fws-from data/pf8_fws.csv     # skip computing it
    python step03b_sample_qc.py --clonal-threshold 0.005
    python step03b_sample_qc.py --no-clonal-pruning --dry-run
"""

from __future__ import annotations

import argparse

import allel
import matplotlib
import numpy as np
import pandas as pd
import zarr

import callset_io as cio

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import config as C  # noqa: E402


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--vcf", default=None,
                   help="Single VCF, or a glob. Defaults to config.GHANA_VCF_GLOB.")
    p.add_argument("--force-zarr", action="store_true")
    p.add_argument("--from-npz", action="store_true",
                   help="Compute call rate and heterozygosity from the cached "
                        ".npz instead of the VCF. Use with --fws-from when the "
                        "callset came from step04a_prepare_callset_malariagen.py.")
    p.add_argument("--n-qc-snps", type=int, default=50_000,
                   help="SNPs subsampled for the per-sample statistics.")
    p.add_argument("--min-ad-depth", type=int, default=5,
                   help="Minimum read depth for a site to contribute to Fws.")

    p.add_argument("--min-fws", type=float, default=C.MIN_FWS)
    p.add_argument("--fws-from", default=None,
                   help="CSV with columns Sample,Fws — used instead of computing it.")
    p.add_argument("--no-fws", action="store_true",
                   help="Skip Fws entirely (no AD field in the VCF, say).")

    p.add_argument("--min-call-rate", type=float, default=C.MIN_SAMPLE_CALL_RATE)
    p.add_argument("--mad-k", type=float, default=3.0,
                   help="MAD multiplier for call-rate and heterozygosity outliers.")
    p.add_argument("--call-rate-mad", action="store_true",
                   help="Also drop samples below the call-rate MAD bound. Off by "
                        "default: with call rates bunched near 1 the bound sits "
                        "around 0.98 and removes perfectly usable samples.")

    p.add_argument("--clonal-threshold", type=float, default=C.CLONAL_THRESHOLD,
                   help="Pairwise distance at or below which two isolates are called "
                        "clonal (default config.CLONAL_THRESHOLD). Pass a negative "
                        "value to use the histogram suggestion instead.")
    p.add_argument("--no-clonal-pruning", action="store_true")

    p.add_argument("--dry-run", action="store_true",
                   help="Report and plot, but write no QC table.")
    return p.parse_args()


# ---------------------------------------------------------------------------
# Zarr access, shared with Step 4a
# ---------------------------------------------------------------------------

def choose_qc_snps(root: zarr.Group, n_target: int) -> pd.DataFrame:
    """A panel of biallelic PASS SNPs spread evenly across every contig.

    Sampling proportionally within each chromosome, rather than taking evenly
    spaced rows from the concatenated table, guards against one long contig
    dominating the panel.
    """
    variants = cio.variant_table(root)
    keep = (variants["filter_pass"].to_numpy()
            & variants["is_snp"].to_numpy()
            & (variants["numalt"].to_numpy() == 1))
    eligible = variants[keep]

    if len(eligible) <= n_target:
        return eligible.reset_index(drop=True)

    share = n_target / len(eligible)
    parts = []
    for _, grp in eligible.groupby("group", sort=False):
        take = max(1, int(round(len(grp) * share)))
        pick = np.linspace(0, len(grp) - 1, take).astype(int)
        parts.append(grp.iloc[pick])
    return pd.concat(parts).sort_values("global").reset_index(drop=True)


def sample_statistics(root: zarr.Group, panel: pd.DataFrame,
                      min_depth: int, want_fws: bool) -> pd.DataFrame:
    ids = cio.samples(root)
    n_samples = len(ids)
    n_panel = len(panel)
    called = np.zeros(n_samples, dtype=np.int64)
    het = np.zeros(n_samples, dtype=np.int64)
    sum_hw = np.zeros(n_samples, dtype=np.float64)
    sum_hs = np.zeros(n_samples, dtype=np.float64)
    fws_sites = np.zeros(n_samples, dtype=np.int64)
    have_ad = want_fws and cio.has_field(root, "calldata/AD")

    chunk = 5_000
    for start in range(0, n_panel, chunk):
        block = panel.iloc[start:start + chunk]

        gt = allel.GenotypeArray(cio.take_calldata(root, block, "calldata/GT"))
        called += gt.is_called().sum(axis=0)
        if gt.ploidy > 1:
            het += gt.is_het().sum(axis=0)

        if have_ad:
            ad = cio.take_calldata(root, block, "calldata/AD", n_alleles=2)
            ad = np.asarray(ad, dtype=np.float64)
            ad[ad < 0] = 0.0
            depth = ad.sum(axis=2)                       # (n_var, n_samp)
            ok = depth >= min_depth

            with np.errstate(invalid="ignore", divide="ignore"):
                q_w = np.where(ok, ad[:, :, 1] / np.maximum(depth, 1), np.nan)
            h_w = 2.0 * q_w * (1.0 - q_w)

            # Population frequency from pooled read counts over qualifying samples.
            alt_pool = np.where(ok, ad[:, :, 1], 0).sum(axis=1)
            tot_pool = np.where(ok, depth, 0).sum(axis=1)
            with np.errstate(invalid="ignore", divide="ignore"):
                q_s = np.where(tot_pool > 0, alt_pool / np.maximum(tot_pool, 1), np.nan)
            h_s = 2.0 * q_s * (1.0 - q_s)

            sum_hw += np.nansum(np.where(ok, h_w, 0.0), axis=0)
            sum_hs += np.nansum(np.where(ok, h_s[:, None], 0.0), axis=0)
            fws_sites += (ok & np.isfinite(h_s[:, None]) & (h_s[:, None] > 0)).sum(axis=0)

        print(f"  {min(start + chunk, n_panel):,}/{n_panel:,} SNPs",
              end="\r", flush=True)
    print()

    stats = pd.DataFrame({
        "Sample": ids,
        "qc_snps_called": called,
        "call_rate": called / n_panel,
        "het_rate": np.divide(het, np.maximum(called, 1)),
    })
    if have_ad:
        with np.errstate(invalid="ignore", divide="ignore"):
            fws = 1.0 - np.divide(sum_hw, np.where(sum_hs > 0, sum_hs, np.nan))
        stats["Fws"] = np.clip(fws, 0.0, 1.0)
        stats["fws_sites"] = fws_sites
    return stats


# ---------------------------------------------------------------------------
# Clonality
# ---------------------------------------------------------------------------

def suggest_clonal_threshold(dist: np.ndarray) -> float | None:
    """Look for a trough separating a clonal spike from the main distribution."""
    iu = np.triu_indices(dist.shape[0], k=1)
    d = dist[iu]
    d = d[np.isfinite(d)]
    if d.size < 20:
        return None
    upper = np.quantile(d, 0.25)
    lower_tail = d[d <= upper]
    if lower_tail.size < 10:
        return None
    counts, edges = np.histogram(lower_tail, bins=60)
    peak = int(np.argmax(counts))
    for i in range(1, peak):
        if counts[i] < counts[i - 1] and counts[i] <= counts[i + 1] and counts[i] > 0:
            return float(edges[i + 1])
    # No trough: fall back to a conservative low quantile.
    return float(np.quantile(d, 0.001))


def clonal_groups(dist: np.ndarray, threshold: float) -> np.ndarray:
    from scipy.sparse import csr_matrix
    from scipy.sparse.csgraph import connected_components

    adj = (dist <= threshold).astype(np.int8)
    np.fill_diagonal(adj, 0)
    _, labels = connected_components(csr_matrix(adj), directed=False)
    return labels


# ---------------------------------------------------------------------------

def mad_bounds(values: np.ndarray, k: float) -> tuple[float, float]:
    v = values[np.isfinite(values)]
    med = float(np.median(v))
    mad = float(np.median(np.abs(v - med))) * 1.4826
    if mad == 0:
        mad = float(np.std(v)) or 1e-9
    return med - k * mad, med + k * mad


def main() -> None:
    args = parse_args()
    C.banner("STEP 3b — sample-level QC")

    meta = pd.read_csv(C.require(C.SAMPLES_AEZ_CSV, "Run step02_assign_aez.py first."))
    meta["Sample"] = meta[C.COL_SAMPLE].astype(str)
    print(f"Samples entering QC: {len(meta):,}")

    # ---- 1. per-sample statistics ----------------------------------------
    C.banner("Call rate, heterozygosity, Fws")
    want_fws = not args.no_fws and args.fws_from is None

    if args.from_npz:
        data = np.load(C.require(C.CALLSET_NPZ,
                                 "Run a step04a variant first."), allow_pickle=False)
        gt = allel.GenotypeArray(data["gt"])
        n_var = gt.n_variants
        print(f"Reading {n_var:,} SNPs x {gt.n_samples:,} samples from "
              f"{C.CALLSET_NPZ.name}")
        stats = pd.DataFrame({
            "Sample": data["samples"].astype(str),
            "qc_snps_called": gt.count_called(axis=0),
            "call_rate": gt.count_called(axis=0) / n_var,
            "het_rate": np.divide(gt.is_het().sum(axis=0),
                                  np.maximum(gt.count_called(axis=0), 1)),
        })
        if args.fws_from:
            supplied = pd.read_csv(C.require(args.fws_from))
            col = next((c for c in supplied.columns if c.lower() == "fws"), None)
            if col is None:
                raise KeyError(f"No Fws column in {args.fws_from}")
            supplied = supplied.rename(columns={col: "Fws"})
            supplied["Sample"] = supplied.iloc[:, 0].astype(str)
            stats = stats.merge(supplied[["Sample", "Fws"]], on="Sample", how="left")
            print(f"Fws merged from {args.fws_from}")
        else:
            print("No --fws-from supplied; the .npz carries no read depths, so")
            print("the monoclonality filter is unavailable on this route.")
    elif args.fws_from:
        supplied = pd.read_csv(C.require(args.fws_from))
        col = next((c for c in supplied.columns if c.lower() == "fws"), None)
        if col is None:
            raise KeyError(f"No Fws column in {args.fws_from}. "
                           f"Columns: {list(supplied.columns)}")
        supplied = supplied.rename(columns={col: "Fws"})
        supplied["Sample"] = supplied.iloc[:, 0].astype(str)
        print(f"Fws read from {args.fws_from} for {len(supplied):,} samples.")
        if not supplied["Sample"].is_unique:
            raise ValueError("Supplied Fws table contains duplicate sample identifiers.")
        root = cio.open_callset(args.vcf, force=args.force_zarr, want_ad=False)
        panel = choose_qc_snps(root, args.n_qc_snps)
        stats = sample_statistics(root, panel, args.min_ad_depth, False)
        stats = stats.merge(supplied[["Sample", "Fws"]], on="Sample", how="left", validate="one_to_one")
    else:
        root = cio.open_callset(args.vcf, force=args.force_zarr, want_ad=want_fws)
        cio.summarise(root)
        panel = choose_qc_snps(root, args.n_qc_snps)
        print(f"\nQC panel: {len(panel):,} biallelic PASS SNPs, proportionally "
              f"spread across {panel['group'].nunique()} contigs")
        if want_fws and not cio.has_field(root, "calldata/AD"):
            print("\ncalldata/AD absent from the VCFs — Fws cannot be computed here.")
            print("Either re-export the subset keeping AD, or supply precomputed")
            print("values with --fws-from (MalariaGEN publishes Fws for Pf8).")
        stats = sample_statistics(root, panel, args.min_ad_depth, want_fws)

    qc = meta.merge(stats, on="Sample", how="left", validate="one_to_one")
    has_fws = "Fws" in qc.columns and qc["Fws"].notna().any()

    if qc["call_rate"].notna().any():
        print(f"\nCall rate:      median {qc['call_rate'].median():.3f}, "
              f"range {qc['call_rate'].min():.3f}–{qc['call_rate'].max():.3f}")
    if qc["het_rate"].notna().any():
        print(f"Het call rate:  median {qc['het_rate'].median():.4f}, "
              f"range {qc['het_rate'].min():.4f}–{qc['het_rate'].max():.4f}")
    if has_fws:
        print(f"Fws:            median {qc['Fws'].median():.3f}, "
              f"range {qc['Fws'].min():.3f}–{qc['Fws'].max():.3f}")
        mono = (qc["Fws"] >= args.min_fws).sum()
        print(f"Monoclonal at Fws >= {args.min_fws}: {mono:,} / {len(qc):,} "
              f"({mono / len(qc):.1%})")
        print("\nPolyclonal fraction by zone (a gradient here is a transmission")
        print("signal, and exactly what would otherwise leak into ADMIXTURE):")
        by_zone = (qc.assign(polyclonal=qc["Fws"] < args.min_fws)
                     .groupby("zone", dropna=False)["polyclonal"]
                     .agg(["size", "sum", "mean"])
                     .rename(columns={"size": "n", "sum": "polyclonal",
                                      "mean": "fraction"}))
        print(by_zone.to_string(float_format=lambda v: f"{v:.3f}"))

    # ---- 2. clonality -----------------------------------------------------
    qc["clonal_group"] = -1
    qc["clonal_representative"] = True
    threshold_used = None

    if not args.no_clonal_pruning:
        C.banner("Clonal and near-identical isolates")
        if not C.GHANA_DIST_NPY.exists():
            print("No cached distance submatrix. Run step03_umap.py first, or pass")
            print("--no-clonal-pruning to skip this check deliberately.")
        else:
            dist = np.load(C.GHANA_DIST_NPY)
            if dist.shape[0] != len(meta):
                print(f"Cached submatrix ({dist.shape[0]}) does not match the sample")
                print(f"table ({len(meta)}). Re-run step03_umap.py --force-reslice.")
            else:
                suggested = suggest_clonal_threshold(dist)
                threshold_used = args.clonal_threshold \
                    if args.clonal_threshold is not None and args.clonal_threshold >= 0 \
                    else suggested
                iu = np.triu_indices(dist.shape[0], k=1)
                d = dist[iu]
                print(f"Pairwise distances: min {d.min():.5f}, "
                      f"1st pct {np.quantile(d, 0.01):.5f}, "
                      f"median {np.median(d):.5f}")
                if suggested is not None:
                    print(f"Suggested clonal threshold from the distance histogram: "
                          f"{suggested:.5f}")
                    print("That is a heuristic. Look at the histogram figure and set")
                    print("--clonal-threshold yourself before relying on it.")

                if threshold_used is not None:
                    labels = clonal_groups(dist, threshold_used)
                    qc["clonal_group"] = labels
                    sizes = pd.Series(labels).value_counts()
                    multi = sizes[sizes > 1]
                    print(f"\nGroups at distance <= {threshold_used:.5f}: "
                          f"{len(multi)} containing {int(multi.sum())} isolates")
                    if len(multi):
                        print(multi.head(10).to_string())

                    # Representative = best call rate, then best Fws, then ID.
                    sort_cols, ascending = ["clonal_group"], [True]
                    for col in ("call_rate", "Fws"):
                        if col in qc.columns and qc[col].notna().any():
                            sort_cols.append(col)
                            ascending.append(False)
                    sort_cols.append("Sample")
                    ascending.append(True)
                    ordered = qc.sort_values(sort_cols, ascending=ascending)
                    keep_idx = ordered.drop_duplicates("clonal_group",
                                                       keep="first").index
                    qc["clonal_representative"] = qc.index.isin(keep_idx)
                    dropped = int((~qc["clonal_representative"]).sum())
                    print(f"Redundant isolates flagged for removal: {dropped}")

    # ---- 3. outlier flags -------------------------------------------------
    C.banner("Outlier flags")
    qc["fail_call_rate"] = False
    qc["fail_call_rate_outlier"] = False
    qc["fail_het_outlier"] = False
    qc["fail_fws"] = False

    if qc["call_rate"].notna().any():
        qc["fail_call_rate"] = qc["call_rate"].isna() | (qc["call_rate"] < args.min_call_rate)
        lo, _ = mad_bounds(qc["call_rate"].to_numpy(), args.mad_k)
        below_mad = qc["call_rate"] < lo
        qc["fail_call_rate_outlier"] = below_mad if args.call_rate_mad else False
        print(f"Call rate below {args.min_call_rate}: "
              f"{int(qc['fail_call_rate'].sum())}")
        print(f"Call rate below MAD bound {lo:.3f}: {int(below_mad.sum())}"
              + ("" if args.call_rate_mad else "  (reported only; --call-rate-mad filters)"))

    if qc["het_rate"].notna().any():
        _, hi = mad_bounds(qc["het_rate"].to_numpy(), args.mad_k)
        qc["fail_het_outlier"] = qc["het_rate"] > hi
        print(f"Heterozygosity above MAD bound {hi:.4f}: "
              f"{int(qc['fail_het_outlier'].sum())}")
        if has_fws:
            print("Largely redundant with Fws here; kept as an independent check.")

    if has_fws:
        qc["fail_fws"] = qc["Fws"].isna() | (qc["Fws"] < args.min_fws)
        print(f"Fws below {args.min_fws}: {int(qc['fail_fws'].sum())}")

    if threshold_used is not None:
        eligible = ~(qc["fail_call_rate"] | qc["fail_call_rate_outlier"]
                     | qc["fail_het_outlier"] | qc["fail_fws"])
        ordered = qc.loc[eligible].sort_values(sort_cols, ascending=ascending)
        keep_idx = ordered.drop_duplicates("clonal_group", keep="first").index
        qc["clonal_representative"] = qc.index.isin(keep_idx)
    qc["fail_clonal"] = ~qc["clonal_representative"]
    qc["qc_pass"] = ~(qc["fail_call_rate"] | qc["fail_call_rate_outlier"]
                      | qc["fail_het_outlier"] | qc["fail_fws"] | qc["fail_clonal"])

    C.banner("QC summary")
    reasons = ["fail_call_rate", "fail_call_rate_outlier", "fail_het_outlier",
               "fail_fws", "fail_clonal"]
    print(f"{'reason':<28} {'n':>6}")
    for r in reasons:
        print(f"  {r:<26} {int(qc[r].sum()):>6}")
    print(f"\nPassing QC: {int(qc['qc_pass'].sum()):,} / {len(qc):,} "
          f"({qc['qc_pass'].mean():.1%})")

    surviving = qc.loc[qc["qc_pass"], "zone"].value_counts(dropna=False)
    print("\nSurviving samples per zone:")
    print(surviving.to_string())
    thin = surviving[surviving < 10]
    if len(thin):
        print(f"\nZones now below n=10: {list(thin.index)}")
        print("Step 4b's --min-zone-n will exclude them. Consider merging them")
        print("with an adjacent zone rather than losing the geography entirely.")

    # ---- 4. figures -------------------------------------------------------
    n_panels = 2 + int(has_fws) + int(threshold_used is not None)
    fig, axes = plt.subplots(1, n_panels, figsize=(4.2 * n_panels, 3.8))
    axes = np.atleast_1d(axes)
    ax = iter(axes)

    a = next(ax)
    if qc["call_rate"].notna().any():
        a.hist(qc["call_rate"].dropna(), bins=40, color="#4c72b0")
        a.axvline(args.min_call_rate, color="crimson", ls="--")
    a.set_xlabel("Call rate")
    a.set_ylabel("Samples")
    a.set_title("Genotype call rate")

    a = next(ax)
    if qc["het_rate"].notna().any() and qc["call_rate"].notna().any():
        colour = qc["Fws"] if has_fws else None
        sc = a.scatter(qc["call_rate"], qc["het_rate"], s=18, c=colour,
                       cmap="viridis", alpha=0.85)
        if has_fws:
            fig.colorbar(sc, ax=a, label="Fws", fraction=0.046)
    a.set_xlabel("Call rate")
    a.set_ylabel("Heterozygous call rate")
    a.set_title("Missingness vs polyclonality")

    if has_fws:
        a = next(ax)
        a.hist(qc["Fws"].dropna(), bins=40, color="#55a868")
        a.axvline(args.min_fws, color="crimson", ls="--",
                  label=f"Fws = {args.min_fws}")
        a.set_xlabel("Fws")
        a.set_ylabel("Samples")
        a.set_title("Within-host fixation index")
        a.legend(fontsize=8)

    if threshold_used is not None:
        a = next(ax)
        dist = np.load(C.GHANA_DIST_NPY)
        d = dist[np.triu_indices(dist.shape[0], k=1)]
        a.hist(d[d <= np.quantile(d, 0.25)], bins=80, color="#c44e52")
        a.axvline(threshold_used, color="black", ls="--",
                  label=f"clonal <= {threshold_used:.4f}")
        a.set_xlabel("Pairwise genotype distance (lower quartile)")
        a.set_ylabel("Pairs")
        a.set_title("Clonal spike")
        a.legend(fontsize=8)

    fig.tight_layout()
    out_png = C.FIG_DIR / "sample_qc.png"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)
    print(f"\nFigure -> {out_png}")

    # ---- 5. write ---------------------------------------------------------
    if args.dry_run:
        print("\n--dry-run: no QC table written.")
        return

    qc.to_csv(C.SAMPLE_QC_FULL_CSV, index=False)
    print(f"Full QC table (all samples, all flags) -> {C.SAMPLE_QC_FULL_CSV}")

    passing = qc[qc["qc_pass"]].drop(columns=[c for c in reasons] + ["qc_pass"])
    passing.to_csv(C.SAMPLES_QC_CSV, index=False)
    print(f"Passing samples -> {C.SAMPLES_QC_CSV}")
    print("Step 4a picks this file up automatically when it exists.")


if __name__ == "__main__":
    main()
