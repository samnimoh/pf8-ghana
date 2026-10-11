#!/usr/bin/env python3
"""
STEP 5c — Plot the ADMIXTURE cross-validation curve and the ancestry barplots.

Samples in each barplot are grouped by agro-ecological zone and sorted within
zone by their dominant component, which is the arrangement that makes a real
geographic signal visible and an absent one obviously absent.

Usage:
    python step05c_plot_admixture.py
    python step05c_plot_admixture.py --best-k 4
"""

from __future__ import annotations

import argparse
import re

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import config as C  # noqa: E402

CV_RE = re.compile(r"CV error \(K=(\d+)\)[:=]?\s*([\d.eE+-]+)")


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--k-min", type=int, default=C.K_MIN)
    p.add_argument("--k-max", type=int, default=C.K_MAX)
    p.add_argument("--best-k", type=int, default=None,
                   help="Override the CV-minimising K for the detailed barplot.")
    p.add_argument("--order-by", default="zone,year",
                   help="Comma-separated sample ordering for the barplots. "
                        "Recognised: zone, year, component. Default zone,year "
                        "follows the method spec; append 'component' to sort "
                        "within group by dominant ancestry.")
    return p.parse_args()


def read_cv(k_min: int, k_max: int) -> dict[int, float]:
    cv: dict[int, float] = {}
    for k in range(k_min, k_max + 1):
        for path in (C.LOG_DIR / f"admixture_K{k}.out",
                     C.ADMIXTURE_DIR / f"log_K{k}.out"):
            if path.exists():
                m = CV_RE.search(path.read_text())
                if m:
                    cv[int(m.group(1))] = float(m.group(2))
                break
    return cv


def main() -> None:
    args = parse_args()
    C.banner("STEP 5c — ADMIXTURE results")

    C.require(C.ADMIXTURE_DIR, "Run step05b_admixture.sh first.")
    meta = pd.read_csv(C.require(C.ANALYSIS_SAMPLES_CSV))

    fam_path = C.ADMIXTURE_DIR / "ghana_pruned.fam"
    fam = pd.read_csv(C.require(fam_path), sep=r"\s+", header=None,
                      names=["fid", "iid", "pid", "mid", "sex", "pheno"])
    order = fam["iid"].astype(str).tolist()
    meta = meta.set_index(meta[C.COL_SAMPLE].astype(str)).reindex(order)
    zones = meta["zone"].fillna("unassigned").to_numpy()

    # ---- CV curve ---------------------------------------------------------
    cv = read_cv(args.k_min, args.k_max)
    if cv:
        ks = sorted(cv)
        vals = [cv[k] for k in ks]
        best_k = args.best_k or ks[int(np.argmin(vals))]

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.plot(ks, vals, marker="o", color="#333")
        ax.scatter([best_k], [cv[best_k]], s=120, facecolors="none",
                   edgecolors="crimson", linewidths=2, zorder=3)
        ax.set_xlabel("K")
        ax.set_ylabel("Cross-validation error")
        ax.set_title(f"ADMIXTURE CV error (minimum at K = {best_k})")
        ax.set_xticks(ks)
        fig.savefig(C.FIG_DIR / "admixture_cv.png", dpi=300, bbox_inches="tight")
        plt.close(fig)

        pd.DataFrame({"K": ks, "cv_error": vals}).to_csv(
            C.ADMIXTURE_DIR / "cv_errors.csv", index=False)
        print("CV error by K:")
        for k, v in zip(ks, vals):
            flag = "  <-- minimum" if k == best_k else ""
            print(f"  K={k}: {v:.5f}{flag}")

        spread = (max(vals) - min(vals)) or 1.0
        flat = [k for k, v in zip(ks, vals) if (v - min(vals)) / spread < 0.05]
        if len(flat) > 1:
            print(f"\nCurve is effectively flat across K = {flat}. Say so in the")
            print("write-up rather than presenting K={best_k} as determined.".format(best_k=best_k))
    else:
        best_k = args.best_k or args.k_min
        print("No CV logs parsed; falling back to K =", best_k)

    # ---- barplots ---------------------------------------------------------
    q_files = sorted(C.ADMIXTURE_DIR.glob("ghana_pruned.*.Q"),
                     key=lambda p: int(p.name.split(".")[-2]))
    if not q_files:
        raise FileNotFoundError(f"No .Q files in {C.ADMIXTURE_DIR}")

    fig, axes = plt.subplots(len(q_files), 1,
                             figsize=(13, 1.7 * len(q_files)), sharex=True)
    axes = np.atleast_1d(axes)

    zone_labels = pd.Index(zones)
    sort_idx = None

    for ax, qf in zip(axes, q_files):
        k = int(qf.name.split(".")[-2])
        q = np.loadtxt(qf)
        if q.ndim == 1:
            q = q.reshape(-1, 1)

        if sort_idx is None:  # fix ordering once, from the smallest K
            frame = pd.DataFrame(q)
            frame["zone"] = zone_labels
            frame["year"] = pd.to_numeric(
                meta[C.COL_YEAR], errors="coerce").to_numpy() \
                if C.COL_YEAR in meta.columns else 0
            frame["dom"] = q.argmax(axis=1)
            frame["domq"] = -q.max(axis=1)

            requested = [t.strip().lower() for t in args.order_by.split(",")]
            key_map = {"zone": ["zone"], "year": ["year"],
                       "component": ["dom", "domq"]}
            sort_keys = [k for tok in requested for k in key_map.get(tok, [])]
            unknown = [t for t in requested if t not in key_map]
            if unknown:
                print(f"Ignoring unrecognised --order-by token(s): {unknown}")
            if not sort_keys:
                sort_keys = ["zone", "year"]
            if C.COL_YEAR not in meta.columns and "year" in requested:
                print(f"No '{C.COL_YEAR}' column — year ordering has no effect.")
            print(f"Sample ordering: {', '.join(sort_keys)}")
            sort_idx = frame.sort_values(sort_keys).index.to_numpy()

        qs = q[sort_idx]
        bottom = np.zeros(len(qs))
        for comp in range(k):
            ax.bar(range(len(qs)), qs[:, comp], bottom=bottom, width=1.0,
                   edgecolor="none")
            bottom += qs[:, comp]
        ax.set_ylabel(f"K={k}", fontsize=9)
        ax.set_xlim(-0.5, len(qs) - 0.5)
        ax.set_ylim(0, 1)
        ax.set_yticks([])
        pd.DataFrame(q, index=order,
                     columns=[f"comp{c+1}" for c in range(k)]).to_csv(
            C.ADMIXTURE_DIR / f"Q_K{k}.csv")

    # Zone boundaries as vertical rules on the bottom panel
    sorted_zones = zone_labels[sort_idx]
    edges, ticks, tick_labels = [], [], []
    start = 0
    for z in pd.unique(sorted_zones):
        width = int((sorted_zones == z).sum())
        edges.append(start + width)
        ticks.append(start + width / 2)
        tick_labels.append(str(z)[:16])
        start += width
    for ax in axes:
        for e in edges[:-1]:
            ax.axvline(e - 0.5, color="white", lw=1.5)
    axes[-1].set_xticks(ticks)
    axes[-1].set_xticklabels(tick_labels, rotation=30, ha="right", fontsize=8)

    fig.suptitle("Ancestry proportions by agro-ecological zone", y=0.995)
    fig.tight_layout()
    out_png = C.FIG_DIR / "admixture_barplots.png"
    fig.savefig(out_png, dpi=300, bbox_inches="tight")
    plt.close(fig)

    print(f"\nFigures -> {C.FIG_DIR / 'admixture_cv.png'}")
    print(f"           {out_png}")
    print(f"Q matrices -> {C.ADMIXTURE_DIR}/Q_K*.csv")


if __name__ == "__main__":
    main()
