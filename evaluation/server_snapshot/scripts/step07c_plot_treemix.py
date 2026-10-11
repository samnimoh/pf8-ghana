#!/usr/bin/env python3
"""
STEP 7c — Summarise the TreeMix sweep: variance explained per m, plus the
residual covariance heatmap for the chosen model.

TreeMix ships R plotting functions; this reimplements the two summaries you
actually need for a methods section in Python, so the whole pipeline stays in
one language.

Variance explained is computed from the fitted versus observed covariance
matrices that TreeMix writes alongside each run. The curve's elbow, not the
likelihood, is what should decide how many edges you keep.

Four populations support only about two identifiable migration edges, so the
sweep (m = 0..5, as the method specifies) is judged twice: within m = 0..2 and
across every m that ran. Both picks go to model_selection.json and onto the
figure, so the choice between them is made at final-analysis time, not here.
The rule in each range: the smallest m whose variance explained reaches 0.998;
failing that, the maximum-likelihood m. Any m that Step 7b recorded as failed
in run_status.tsv is skipped.

Usage:
    python step07c_plot_treemix.py
    python step07c_plot_treemix.py --m 2
"""

from __future__ import annotations

import argparse
import gzip
import json

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import config as C  # noqa: E402

# Edges beyond this are poorly identifiable with four populations. Keep in step
# with IDENT_MAX_M in step07b_treemix.sh.
IDENTIFIABLE_MAX_M = 2
VE_THRESHOLD = 0.998            # Pickrell & Pritchard (2012)
VE_PLATEAU = 0.001              # fallback: within this of the range's best VE
OK_STATUSES = {"ok", "cached"}  # run_status.tsv values that mean usable output


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--max-m", type=int, default=None,
                   help="Highest m to read (default: every m in run_status.tsv, "
                        "else TREEMIX_MAX_M).")
    p.add_argument("--m", type=int, default=None,
                   help="Which model to draw the residual heatmap for "
                        "(default: the picks in model_selection.json).")
    return p.parse_args()


def read_cov(path) -> pd.DataFrame | None:
    if not path.exists():
        return None
    with gzip.open(path, "rt") as fh:
        return pd.read_csv(fh, sep=r"\s+", index_col=0)


def read_llik(m: int) -> float:
    """Last field of the last line. TreeMix 1.13 writes .llik uncompressed."""
    for path, opener in ((C.TREEMIX_DIR / f"treemix_m{m}.llik.gz", gzip.open),
                         (C.TREEMIX_DIR / f"treemix_m{m}.llik", open)):
        if not path.exists():
            continue
        with opener(path, "rt") as fh:
            tail = [ln for ln in fh if ln.strip()]
        if tail:
            try:
                return float(tail[-1].split()[-1])
            except ValueError:
                pass
    return np.nan


def read_run_status() -> dict[int, tuple[str, str]]:
    """m -> (status, exit_code) as Step 7b recorded it; empty if 7b predates it."""
    path = C.TREEMIX_DIR / "run_status.tsv"
    if not path.exists():
        return {}
    st = pd.read_csv(path, sep="\t", dtype=str, keep_default_na=False)
    return {int(r.m): (r.status, r.exit_code) for r in st.itertuples(index=False)}


def variance_explained(obs: pd.DataFrame, fitted: pd.DataFrame) -> float:
    """TreeMix's f (Pickrell & Pritchard 2012): the share of variance in
    between-population relatedness that the model accounts for. Off-diagonal
    pairs only, as in TreeMix's get_f(); the 0.998 rule of thumb assumes that
    definition, and including the diagonal would inflate it."""
    o = obs.to_numpy().astype(float)
    f = fitted.reindex(index=obs.index, columns=obs.columns).to_numpy().astype(float)
    iu = np.triu_indices_from(o, k=1)
    resid = o[iu] - f[iu]
    return 1.0 - (np.nanvar(resid) / np.nanvar(o[iu]))


def _num(v) -> float | None:
    """NaN -> None, so the JSON stays valid."""
    return None if pd.isna(v) else float(v)


def pick_m(summary: pd.DataFrame, hi: int) -> dict:
    """Smallest m in 0..hi reaching VE_THRESHOLD, else the start of the plateau.

    Likelihood never falls as edges are added, so "maximum likelihood" would
    always return the largest m tried. The fallback instead takes the smallest
    m whose variance explained is within VE_PLATEAU of the best in the range.
    """
    sub = summary[(summary["m"] <= hi) & summary["variance_explained"].notna()]
    considered = [int(v) for v in sub["m"]]
    if sub.empty:
        return {"m_range": [0, hi], "m": None,
                "basis": "no successful run in this range", "m_considered": considered}
    hit = sub[sub["variance_explained"] >= VE_THRESHOLD]
    if not hit.empty:
        row = hit.loc[hit["m"].idxmin()]
        basis = f"smallest m with variance explained >= {VE_THRESHOLD}"
    else:
        best = sub["variance_explained"].max()
        flat = sub[sub["variance_explained"] >= best - VE_PLATEAU]
        row = flat.loc[flat["m"].idxmin()]
        basis = (f"no m reached {VE_THRESHOLD}; smallest m within {VE_PLATEAU} "
                 f"of the best variance explained in 0..{hi} ({best:.4f})")
    return {"m_range": [0, hi], "m": int(row["m"]), "basis": basis,
            "variance_explained": _num(row["variance_explained"]),
            "log_likelihood": _num(row["log_likelihood"]),
            "m_considered": considered}


def mark_ranges(ax, max_m: int, skipped: dict[int, str]) -> None:
    """Shade the identifiable range and draw the cut, so the two views read apart."""
    ax.axvspan(-0.5, IDENTIFIABLE_MAX_M + 0.5, color="#e3ebf3", lw=0, zorder=0,
               label=f"m ≤ {IDENTIFIABLE_MAX_M}: identifiable with 4 populations")
    if max_m > IDENTIFIABLE_MAX_M:
        ax.axvline(IDENTIFIABLE_MAX_M + 0.5, color="0.35", ls="--", lw=1,
                   label=f"m > {IDENTIFIABLE_MAX_M}: poorly identifiable")
    ax.set_xlim(-0.5, max_m + 0.5)
    # Every m attempted gets a tick; ones with no usable run say why.
    ax.set_xticks(range(max_m + 1),
                  [f"{m}\n({skipped[m]})" if m in skipped else str(m)
                   for m in range(max_m + 1)])


def mark_picks(ax, summary: pd.DataFrame, col: str, picks: dict[str, int | None]) -> None:
    """Ring the m chosen within each range; a single ring when both agree."""
    chosen: dict[int, list[str]] = {}
    for name, m in picks.items():
        if m is not None:
            chosen.setdefault(m, []).append(name)
    for (m, names), marker in zip(chosen.items(), ("o", "D")):
        y = summary.loc[summary["m"] == m, col]
        if y.empty or y.isna().all():
            continue
        ax.scatter([m], [float(y.iloc[0])], s=170, marker=marker, facecolors="none",
                   edgecolors="#d9822b", linewidths=1.6, zorder=3,
                   label=f"selected m ({' and '.join(names)})")


def draw_residuals(m: int) -> None:
    """Residual heatmap, residual CSV and Newick tree for one m."""
    obs = read_cov(C.TREEMIX_DIR / f"treemix_m{m}.cov.gz")
    fit = read_cov(C.TREEMIX_DIR / f"treemix_m{m}.modelcov.gz")
    resid = obs - fit.reindex(index=obs.index, columns=obs.columns)

    lim = float(np.nanmax(np.abs(resid.to_numpy())))
    fig, ax = plt.subplots(figsize=(6.5, 5.5))
    im = ax.imshow(resid.to_numpy(), cmap="RdBu_r", vmin=-lim, vmax=lim)
    labs = [str(i)[:16] for i in resid.index]
    ax.set_xticks(range(len(labs)), labs, rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(labs)), labs, fontsize=8)
    fig.colorbar(im, ax=ax, label="Residual covariance", fraction=0.046)
    ax.set_title(f"TreeMix residuals, m = {m}")
    fig.savefig(C.FIG_DIR / f"treemix_residuals_m{m}.png", dpi=300,
                bbox_inches="tight")
    plt.close(fig)
    resid.to_csv(C.TREEMIX_DIR / f"residuals_m{m}.csv")
    print(f"\nResidual heatmap drawn for m = {m}")

    # ---- the tree itself --------------------------------------------------
    tree_path = C.TREEMIX_DIR / f"treemix_m{m}.treeout.gz"
    if tree_path.exists():
        with gzip.open(tree_path, "rt") as fh:
            lines = [ln.strip() for ln in fh if ln.strip()]
        newick = lines[0]
        (C.TREEMIX_DIR / f"treemix_m{m}.nwk").write_text(newick + "\n")
        print(f"Newick tree -> {C.TREEMIX_DIR}/treemix_m{m}.nwk")
        if len(lines) > 1:
            print("Migration edges (weight, jackknife SE, p):")
            for ln in lines[1:]:
                print("  " + ln)


def main() -> None:
    args = parse_args()
    C.banner("STEP 7c — TreeMix summaries")

    C.require(C.TREEMIX_DIR, "Run step07b_treemix.sh first.")

    status = read_run_status()
    if status:
        print(f"Run status from Step 7b: {C.TREEMIX_DIR / 'run_status.tsv'}")
    else:
        print("No run_status.tsv from Step 7b; judging each m by its output files.")
    max_m = args.max_m if args.max_m is not None else (
        max(status) if status else C.TREEMIX_MAX_M)

    rows, comp_rows, npop = [], [], None
    for m in range(0, max_m + 1):
        st, code = status.get(m, (None, "NA"))
        ve = llik = np.nan
        # A run 7b marked failed is ignored even if it left partial files.
        if st is None or st in OK_STATUSES:
            obs = read_cov(C.TREEMIX_DIR / f"treemix_m{m}.cov.gz")
            fit = read_cov(C.TREEMIX_DIR / f"treemix_m{m}.modelcov.gz")
            if obs is not None and fit is not None:
                ve, llik, npop = variance_explained(obs, fit), read_llik(m), obs.shape[0]
                rows.append({"m": m,
                             "variance_explained": ve,
                             "log_likelihood": llik})
                st = st or "ok"
            else:
                st = "missing_output" if st else "missing"
        if st not in OK_STATUSES:
            exit_note = f", exit {code}" if code not in ("", "NA") else ""
            print(f"  m={m}: skipped ({st}{exit_note})")
        comp_rows.append({"m": m,
                          "log_likelihood": llik,
                          "variance_explained": ve,
                          "status": st,
                          "identifiable_4pops": m <= IDENTIFIABLE_MAX_M})

    if not rows:
        raise FileNotFoundError(
            f"No usable treemix_m*.cov.gz / .modelcov.gz in {C.TREEMIX_DIR} "
            "(see run_status.tsv). Did Step 7b finish?")

    summary = pd.DataFrame(rows)
    summary.to_csv(C.TREEMIX_DIR / "variance_explained.csv", index=False)
    comparison = pd.DataFrame(comp_rows)
    comparison.to_csv(C.TREEMIX_DIR / "model_comparison.csv", index=False)
    print(comparison.to_string(index=False, float_format=lambda v: f"{v:.5f}"))
    bad = comparison[~comparison["status"].isin(OK_STATUSES)]
    skipped = {int(m): st for m, st in zip(bad["m"], bad["status"])}

    # ---- model choice within each range -----------------------------------
    ident = pick_m(summary, IDENTIFIABLE_MAX_M)
    full = pick_m(summary, max_m)
    if npop is not None and npop != 4:
        print(f"\nWARNING: {npop} populations, but IDENTIFIABLE_MAX_M = "
              f"{IDENTIFIABLE_MAX_M} assumes 4. Revisit it before using the 0–2 pick.")
    selection = {
        "rule": (f"smallest m with variance explained >= {VE_THRESHOLD}; otherwise "
                 f"the smallest m within {VE_PLATEAU} of the range's best (plateau)"),
        "variance_explained_threshold": VE_THRESHOLD,
        "variance_explained_definition": ("1 - var(observed - fitted) / var(observed), "
                                          "over off-diagonal (between-population) "
                                          "covariances, as TreeMix's get_f()"),
        "n_populations": npop,
        "m_succeeded": [int(v) for v in summary["m"]],
        "m_skipped": [int(v) for v in skipped],
        "identifiable_max_m": IDENTIFIABLE_MAX_M,
        "identifiable_range": ident,
        "full_range": full,
        "note": (f"With 4 populations TreeMix supports at most ~{IDENTIFIABLE_MAX_M} "
                 f"identifiable migration edges. m = 0..{max_m} was run as the method "
                 f"specifies; picks with m > {IDENTIFIABLE_MAX_M} should be interpreted "
                 "with caution."),
    }
    (C.TREEMIX_DIR / "model_selection.json").write_text(
        json.dumps(selection, indent=2) + "\n")
    print(f"\nSelected m within 0–{IDENTIFIABLE_MAX_M} (identifiable): "
          f"{ident['m']}  [{ident['basis']}]")
    print(f"Selected m within 0–{max_m} (full sweep):   {full['m']}  [{full['basis']}]")
    print(f"Selection -> {C.TREEMIX_DIR}/model_selection.json")

    picks = {f"0–{IDENTIFIABLE_MAX_M}": ident["m"], f"0–{max_m}": full["m"]}
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4))
    ax1.plot(summary["m"], summary["variance_explained"], marker="o", color="#1f4e79")
    ax1.axhline(VE_THRESHOLD, color="0.5", ls=":", lw=1,
                label=f"variance explained = {VE_THRESHOLD}")
    mark_ranges(ax1, max_m, skipped)
    mark_picks(ax1, summary, "variance_explained", picks)
    ax1.set_xlabel("Migration edges (m)")
    ax1.set_ylabel("Variance explained")
    ax1.set_title("Fit vs model complexity")
    ax1.legend(fontsize=7, loc="best", framealpha=0.9)
    ax2.plot(summary["m"], summary["log_likelihood"], marker="s", color="#8b1a1a")
    mark_ranges(ax2, max_m, skipped)
    mark_picks(ax2, summary, "log_likelihood", picks)
    ax2.set_xlabel("Migration edges (m)")
    ax2.set_ylabel("Log likelihood")
    ax2.set_title("Likelihood rises with m by construction")
    ax2.legend(fontsize=7, loc="best", framealpha=0.9)
    fig.tight_layout()
    fig.savefig(C.FIG_DIR / "treemix_variance_explained.png", dpi=300,
                bbox_inches="tight")
    plt.close(fig)

    # ---- residual heatmap for the chosen model(s) --------------------------
    if args.m is not None:
        if args.m not in summary["m"].tolist():
            raise SystemExit(f"--m {args.m}: no usable TreeMix output for that m. "
                             f"Available: {summary['m'].tolist()}")
        targets = [args.m]
    else:
        targets = list(dict.fromkeys(p["m"] for p in (ident, full) if p["m"] is not None))
    for m in targets:
        draw_residuals(m)

    print("\nPositive residuals mark population pairs more closely related than the")
    print("tree alone predicts — candidate destinations for an additional edge.")
    print(f"\nFigures -> {C.FIG_DIR}/treemix_*.png")


if __name__ == "__main__":
    main()
