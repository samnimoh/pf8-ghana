#!/usr/bin/env python3
"""
STEP 3 — UMAP, t-SNE and PCoA of the Ghanaian block of the Pf8 mean genotype
distance matrix, side by side.

The global matrix is ~4.4 GB. Memory-mapping it and pulling out only the rows
and columns you need keeps peak RSS in the low hundreds of megabytes, which
matters more in WSL than it did in Colab: WSL2 takes its RAM from Windows, and
an eager load can push the whole machine into swap.

Indexing uses the `pf8_row` column captured in Step 1, never the pandas index.

All three methods read the same submatrix, so differences between the plots
come from the methods, not the data:

  UMAP   — local neighbourhoods, with some global layout. Cluster sizes and gaps
           are not quantitative.
  t-SNE  — local neighbourhoods only; between-cluster distances mean nothing.
  PCoA   — classical metric MDS. Linear, so it keeps the large-scale distances,
           and each axis comes with the share of variation it explains.

A comparison table scores each embedding on the same footing: trustworthiness
(are near neighbours in 2-D also near in the full matrix), rank correlation of
pairwise distances (global structure), and silhouette by zone (how cleanly the
colour groups separate).

Usage:
    python step03_umap.py
    python step03_umap.py --methods umap pcoa
    python step03_umap.py --n-neighbors 15 --min-dist 0.05 --perplexity 50
    python step03_umap.py --colour-by "Admin level 1"
    python step03_umap.py --force-reslice
"""

from __future__ import annotations

import argparse

import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

import config as C  # noqa: E402

METHODS = ("umap", "tsne", "pcoa")
AXIS_LABELS = {"umap": ("UMAP 1", "UMAP 2"), "tsne": ("t-SNE 1", "t-SNE 2")}
TITLES = {"umap": "UMAP", "tsne": "t-SNE", "pcoa": "PCoA"}


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--methods", nargs="+", choices=METHODS, default=list(METHODS),
                   help="Which embeddings to compute (default: all three).")
    p.add_argument("--n-neighbors", type=int, default=C.UMAP_N_NEIGHBORS)
    p.add_argument("--min-dist", type=float, default=C.UMAP_MIN_DIST)
    p.add_argument("--perplexity", type=float, default=C.TSNE_PERPLEXITY)
    p.add_argument("--pcoa-axes", type=int, default=C.PCOA_N_AXES,
                   help="PCoA axes written to the coordinates table.")
    p.add_argument("--threads", type=int, default=8,
                   help="Worker threads for t-SNE (shared server: keep modest).")
    p.add_argument("--colour-by", default="zone",
                   help="Column in the Step 2 output used for point colour.")
    p.add_argument("--no-metrics", action="store_true",
                   help="Skip the comparison scores.")
    p.add_argument("--force-reslice", action="store_true",
                   help="Re-extract the Ghana submatrix even if cached.")
    return p.parse_args()


def extract_submatrix(pf8_rows: np.ndarray) -> np.ndarray:
    """Slice the Ghanaian block out of the global matrix without loading it."""
    C.require(
        C.DIST_MATRIX,
        "Expected Pf8_mean_genotype_distance.npy in data/ "
        "(Zenodo record 18681980, ~4.4 GB).",
    )
    print(f"Memory-mapping {C.DIST_MATRIX.name} "
          f"({C.DIST_MATRIX.stat().st_size / 1e9:.2f} GB on disk)")

    full = np.load(C.DIST_MATRIX, mmap_mode="r")
    print(f"Global matrix shape: {full.shape}, dtype {full.dtype}")

    if full.ndim != 2 or full.shape[0] != full.shape[1]:
        raise ValueError(f"Expected a square matrix, got shape {full.shape}.")
    if pf8_rows.max() >= full.shape[0]:
        raise IndexError(
            f"pf8_row max ({pf8_rows.max()}) exceeds matrix dimension "
            f"({full.shape[0]}). The manifest and the matrix are out of sync — "
            f"check you have the Pf8 release of both, not Pf7."
        )

    sub = np.asarray(full[np.ix_(pf8_rows, pf8_rows)], dtype=np.float32)
    del full
    return sub


# ---------------------------------------------------------------------------
# The three embeddings
# ---------------------------------------------------------------------------

def run_umap(dist: np.ndarray, n_neighbors: int, min_dist: float) -> np.ndarray:
    import umap  # imported late; it pulls in numba and is slow to load

    reducer = umap.UMAP(
        n_neighbors=n_neighbors,
        min_dist=min_dist,
        metric="precomputed",
        random_state=C.RANDOM_SEED,
    )
    print("Fitting UMAP...", flush=True)
    return reducer.fit_transform(dist)


def run_tsne(dist: np.ndarray, perplexity: float, threads: int) -> np.ndarray:
    from sklearn.manifold import TSNE

    n = dist.shape[0]
    perplexity = min(perplexity, max(5.0, (n - 1) / 3.0))
    # init="pca" needs feature vectors; with precomputed distances it must be random.
    tsne = TSNE(n_components=2, metric="precomputed", init="random",
                perplexity=perplexity, random_state=C.RANDOM_SEED, n_jobs=threads)
    print(f"Fitting t-SNE (perplexity {perplexity:g})...", flush=True)
    return tsne.fit_transform(dist.astype(np.float64))


def run_pcoa(dist: np.ndarray, n_axes: int) -> tuple[np.ndarray, pd.DataFrame]:
    """Classical (metric) MDS: Gower double-centring, then an eigendecomposition."""
    from scipy.linalg import eigh

    print("Running PCoA...", flush=True)
    d2 = dist.astype(np.float64) ** 2
    b = -0.5 * (d2 - d2.mean(axis=1, keepdims=True) - d2.mean(axis=0, keepdims=True)
                + d2.mean())
    del d2
    evals, evecs = eigh(b)
    del b
    order = np.argsort(evals)[::-1]
    evals, evecs = evals[order], evecs[:, order]

    positive = evals[evals > 0].sum()
    n_axes = min(n_axes, int((evals > 0).sum()))
    coords = evecs[:, :n_axes] * np.sqrt(evals[:n_axes])

    neg = evals[evals < 0]
    if neg.size and abs(neg.sum()) > 1e-6 * positive:
        print(f"  {neg.size} negative eigenvalues (sum {neg.sum():.3g} vs positive "
              f"{positive:.3g}): the distance is not perfectly Euclidean. Proportions "
              f"below are relative to the positive eigenvalues, the usual convention.")

    prop = evals[:n_axes] / positive
    eig = pd.DataFrame({
        "axis": [f"PC{i + 1}" for i in range(n_axes)],
        "eigenvalue": evals[:n_axes],
        "proportion_explained": prop,
        "cumulative": np.cumsum(prop),
    })
    print("  " + ", ".join(f"PC{i + 1} {p:.1%}" for i, p in enumerate(prop[:5])))
    return coords, eig


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------

def compare(dist: np.ndarray, embeddings: dict[str, np.ndarray],
            labels: np.ndarray, n_neighbors: int) -> pd.DataFrame:
    from scipy.spatial.distance import pdist
    from scipy.stats import spearmanr
    from sklearn.manifold import trustworthiness
    from sklearn.metrics import silhouette_score

    n = dist.shape[0]
    k = max(1, min(n_neighbors, n // 2 - 1))
    rng = np.random.default_rng(C.RANDOM_SEED)
    sub = rng.choice(n, size=min(n, 2000), replace=False)
    iu = np.triu_indices(len(sub), k=1)
    d_ref = dist[np.ix_(sub, sub)][iu]

    multi = len(np.unique(labels)) > 1
    rows = []
    if multi:
        rows.append({"method": "original distances", "trustworthiness": np.nan,
                     "distance_spearman": 1.0,
                     "silhouette_by_zone": silhouette_score(dist, labels,
                                                            metric="precomputed")})
    for name, emb in embeddings.items():
        e2 = emb[:, :2]
        print(f"  scoring {TITLES[name]}...", flush=True)
        rows.append({
            "method": TITLES[name],
            "trustworthiness": trustworthiness(dist, e2, n_neighbors=k,
                                               metric="precomputed"),
            "distance_spearman": spearmanr(d_ref, pdist(e2[sub])).statistic,
            "silhouette_by_zone": silhouette_score(e2, labels) if multi else np.nan,
        })
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Plotting
# ---------------------------------------------------------------------------

def scatter_groups(ax, emb: np.ndarray, codes: np.ndarray, labels, colours) -> None:
    # Largest groups first, so small zones are drawn on top rather than buried.
    sizes = np.bincount(codes, minlength=len(labels))
    for i in np.argsort(sizes)[::-1]:
        m = codes == i
        ax.scatter(emb[m, 0], emb[m, 1], s=10, alpha=0.7, color=colours[i],
                   linewidths=0, label=f"{labels[i]} (n={int(m.sum())})")


def axis_labels(name: str, eig: pd.DataFrame | None) -> tuple[str, str]:
    if name == "pcoa" and eig is not None:
        p = eig["proportion_explained"].to_numpy()
        return f"PC1 ({p[0]:.1%})", f"PC2 ({p[1]:.1%})"
    return AXIS_LABELS[name]


def main() -> None:
    args = parse_args()
    C.set_seeds()
    C.banner("STEP 3 — UMAP, t-SNE and PCoA on the Ghana distance submatrix")

    C.require(C.SAMPLES_AEZ_CSV, "Run step02_assign_aez.py first.")
    samples = pd.read_csv(C.SAMPLES_AEZ_CSV)
    pf8_rows = samples["pf8_row"].to_numpy(dtype=np.int64)

    if C.GHANA_DIST_NPY.exists() and not args.force_reslice:
        dist = np.load(C.GHANA_DIST_NPY)
        print(f"Loaded cached submatrix {dist.shape} from {C.GHANA_DIST_NPY.name}")
        if dist.shape[0] != len(samples):
            raise ValueError(
                f"Cached submatrix ({dist.shape[0]}) does not match the current "
                f"sample table ({len(samples)}). Re-run with --force-reslice."
            )
    else:
        dist = extract_submatrix(pf8_rows)
        np.save(C.GHANA_DIST_NPY, dist)
        print(f"Ghana submatrix {dist.shape} cached -> {C.GHANA_DIST_NPY}")

    # Precomputed metrics require a clean symmetric matrix.
    if not np.allclose(dist, dist.T, atol=1e-5, equal_nan=True):
        print("Matrix not perfectly symmetric — symmetrising as (D + D.T) / 2")
        dist = (dist + dist.T) / 2.0
    np.fill_diagonal(dist, 0.0)
    if np.isnan(dist).any():
        n_nan = int(np.isnan(dist).sum())
        print(f"WARNING: {n_nan} NaN entries replaced with the matrix mean.")
        dist = np.nan_to_num(dist, nan=float(np.nanmean(dist)))

    n = dist.shape[0]
    n_neighbors = min(args.n_neighbors, max(2, n - 1))
    if n_neighbors != args.n_neighbors:
        print(f"n_neighbors reduced to {n_neighbors} (only {n} samples).")

    colour_col = args.colour_by if args.colour_by in samples.columns else "zone"
    labels_series = samples[colour_col].fillna("unassigned")
    codes, labels = pd.factorize(labels_series)
    colours = plt.get_cmap("tab10" if len(labels) <= 10 else "tab20")(
        np.arange(len(labels)) % (10 if len(labels) <= 10 else 20))
    slug = C.slugify_zone(colour_col).lower()

    id_cols = [C.COL_SAMPLE, "pf8_row", "zone"] if C.COL_SAMPLE in samples.columns \
        else ["pf8_row", "zone"]

    # ---- embeddings -------------------------------------------------------
    embeddings: dict[str, np.ndarray] = {}
    eig = None
    for method in args.methods:
        C.banner(TITLES[method])
        if method == "umap":
            emb = run_umap(dist, n_neighbors, args.min_dist)
            out = samples[id_cols].copy()
            out["umap1"], out["umap2"] = emb[:, 0], emb[:, 1]
            out.to_csv(C.UMAP_EMBEDDING_CSV, index=False)
            print(f"Coordinates -> {C.UMAP_EMBEDDING_CSV}")
        elif method == "tsne":
            emb = run_tsne(dist, args.perplexity, args.threads)
            out = samples[id_cols].copy()
            out["tsne1"], out["tsne2"] = emb[:, 0], emb[:, 1]
            out.to_csv(C.TSNE_EMBEDDING_CSV, index=False)
            print(f"Coordinates -> {C.TSNE_EMBEDDING_CSV}")
        else:
            emb, eig = run_pcoa(dist, args.pcoa_axes)
            out = samples[id_cols].copy()
            for i in range(emb.shape[1]):
                out[f"PC{i + 1}"] = emb[:, i]
            out.to_csv(C.PCOA_COORDS_CSV, index=False)
            eig.to_csv(C.PCOA_EIGEN_CSV, index=False)
            print(f"Coordinates -> {C.PCOA_COORDS_CSV}")
            print(f"Eigenvalues -> {C.PCOA_EIGEN_CSV}")
        embeddings[method] = emb

        fig, ax = plt.subplots(figsize=(8.5, 6.5))
        scatter_groups(ax, emb, codes, labels, colours)
        ax.legend(fontsize=7, markerscale=1.8, frameon=False,
                  loc="center left", bbox_to_anchor=(1.01, 0.5))
        xl, yl = axis_labels(method, eig)
        ax.set_xlabel(xl)
        ax.set_ylabel(yl)
        ax.set_title(f"Ghana P. falciparum structure (Pf8), {TITLES[method]}, "
                     f"coloured by {colour_col}")
        out_png = C.FIG_DIR / f"{method}_ghana_{slug}.png"
        fig.savefig(out_png, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"Figure -> {out_png}")

    # ---- side-by-side comparison -----------------------------------------
    if len(embeddings) > 1:
        C.banner("Comparison")
        fig, axes = plt.subplots(1, len(embeddings), figsize=(5.2 * len(embeddings), 4.8))
        for ax, (method, emb) in zip(np.atleast_1d(axes), embeddings.items()):
            scatter_groups(ax, emb, codes, labels, colours)
            xl, yl = axis_labels(method, eig)
            ax.set_xlabel(xl)
            ax.set_ylabel(yl)
            ax.set_title(TITLES[method])
        handles, leg = np.atleast_1d(axes)[0].get_legend_handles_labels()
        fig.legend(handles, leg, loc="lower center", ncol=min(len(leg), 5),
                   fontsize=8, markerscale=1.8, frameon=False)
        fig.suptitle(f"Ghana P. falciparum (Pf8): same distances, three embeddings "
                     f"(coloured by {colour_col})")
        fig.tight_layout(rect=(0, 0.08, 1, 0.95))
        out_png = C.FIG_DIR / f"dimred_comparison_{slug}.png"
        fig.savefig(out_png, dpi=300, bbox_inches="tight")
        plt.close(fig)
        print(f"Figure -> {out_png}")

        if not args.no_metrics:
            table = compare(dist, embeddings, codes, n_neighbors)
            table.to_csv(C.DIMRED_COMPARISON_CSV, index=False)
            print()
            print(table.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
            print(f"\nScores -> {C.DIMRED_COMPARISON_CSV}")
            print("trustworthiness: 1 = every 2-D neighbour is a true neighbour.")
            print("distance_spearman: rank agreement of pairwise distances "
                  "(global structure).")
            print("silhouette_by_zone: > 0 means zones separate; near 0 means they "
                  "overlap.")

    print("\nUMAP and t-SNE distances between clusters carry no quantitative "
          "meaning. Read cluster membership, not separation width. PCoA axes "
          "are linear and their spacing is interpretable.")


if __name__ == "__main__":
    main()
