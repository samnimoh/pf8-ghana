#!/usr/bin/env python3
"""
STEP 3a — Fetch the Ghana callset straight from the Pf8 Zarr on Sanger.

Replaces the per-chromosome VCF download. The Pf8 release publishes the whole
callset (33,325 samples x 12.5M variants) as a Zarr store over HTTPS, chunked
131,072 variants x 100 samples. This script downloads only the chunks that hold
Ghana samples and keeps only what Steps 3b and 4a read — PASS biallelic SNPs
with GT, AD (REF + ALT), DP and GQ — writing them into interim/pf8_ghana.zarr in
the same per-contig layout callset_io builds from VCFs. Steps 3b and 4a then use
that store as it is; no VCF needs to be on disk.

Every PASS site in Pf8 has RegionType "Core", so the PASS filter already does
the job the optional core-region BED does on the VCF route.

One chunk at a time is fetched, decompressed, trimmed and written, so memory
stays at a few GB and only the trimmed result reaches the disk.

The store is built at pf8_ghana.zarr.partial and renamed only once every chunk
is written, so an interrupted run never leaves a half-filled store that later
steps would mistake for a finished one. Rerun to resume: completed variant
chunks are skipped.

Usage:
    python step03a_fetch_callset_zarr.py                   # 8 parallel downloads
    python step03a_fetch_callset_zarr.py --threads 4       # gentler on a shared link
    python step03a_fetch_callset_zarr.py --force           # rebuild from scratch

    # Trial on one region, written elsewhere and checked against a local VCF:
    python step03a_fetch_callset_zarr.py --region Pf3D7_10_v3:400001-440000 \\
        --out ../interim/_trial.zarr \\
        --validate-vcf ../data/Pf8_Ghana_Pf3D7_10_v3.vcf.gz

    # Check an existing store against a VCF without fetching anything:
    python step03a_fetch_callset_zarr.py --validate-only \\
        --validate-vcf ../data/Pf8_Ghana_Pf3D7_10_v3.vcf.gz \\
        --validate-region Pf3D7_10_v3:400001-440000
"""

from __future__ import annotations

import argparse
import concurrent.futures as cf
import hashlib
import itertools
import json
import shutil
import threading
import time
from pathlib import Path

import numcodecs
import numpy as np
import requests
import zarr
from urllib3.util.retry import Retry

import config as C

PF8_ZARR_URL = "https://pf8-release.cog.sanger.ac.uk/zarr"
DEFAULT_SAMPLE_LIST = C.DATA_DIR / "ghana_samples.txt"
DEFAULT_VALIDATE_REGION = "Pf3D7_10_v3:400001-440000"

# calldata field -> trailing-axis length kept (None for 2-D fields).
# AD keeps REF + first ALT, which is everything at a biallelic site.
CALLDATA = {"GT": 2, "AD": 2, "DP": None, "GQ": None}
VARIANT_FIELDS = ["CHROM", "POS", "REF", "ALT", "numalt", "is_snp", "FILTER_PASS"]

OUT_VARIANT_CHUNK = 16384
OUT_SAMPLE_CHUNK = 512


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--threads", type=int, default=8,
                   help="Parallel downloads. 8 is ~20 MB/s; 24 is ~33 MB/s.")
    p.add_argument("--samples", default=str(DEFAULT_SAMPLE_LIST),
                   help="One sample ID per line.")
    p.add_argument("--out", default=None,
                   help="Store to write. Defaults to config.CALLSET_ZARR.")
    p.add_argument("--region", default=None,
                   help="Restrict to CONTIG or CONTIG:START-END (for trials).")
    p.add_argument("--force", action="store_true",
                   help="Delete any existing or partial store and start again.")
    p.add_argument("--validate-vcf", default=None,
                   help="After building, compare the store with this VCF.")
    p.add_argument("--validate-region", default=None,
                   help=f"Region for --validate-vcf (default {DEFAULT_VALIDATE_REGION}, "
                        f"or --region when given).")
    p.add_argument("--validate-only", action="store_true",
                   help="Skip fetching; only run the comparison on --out.")
    return p.parse_args()


def parse_region(text: str) -> tuple[str, int | None, int | None]:
    contig, _, span = text.partition(":")
    if not span:
        return contig, None, None
    start, end = span.replace(",", "").split("-")
    return contig, int(start), int(end)


# ---------------------------------------------------------------------------
# HTTP access to the remote store
# ---------------------------------------------------------------------------

class Remote:
    """GETs keys of a Zarr store served over HTTPS, with retries and a byte count."""

    def __init__(self, base: str, threads: int):
        self.base = base.rstrip("/")
        self.pool_size = max(4, threads * 2)
        self._local = threading.local()
        self._lock = threading.Lock()
        self.bytes = 0
        self.missing: list[str] = []

    def _session(self) -> requests.Session:
        s = getattr(self._local, "session", None)
        if s is None:
            s = requests.Session()
            # Sanger closes idle keep-alive connections, so a pooled connection
            # is sometimes dead on reuse. urllib3 retries those at once on a fresh
            # connection; get() below backs off only for real outages.
            quick = Retry(total=3, connect=3, read=3, status=3, backoff_factor=0.5,
                          status_forcelist=(429, 500, 502, 503, 504),
                          allowed_methods=frozenset({"GET", "HEAD"}),
                          raise_on_status=False)
            adapter = requests.adapters.HTTPAdapter(pool_connections=self.pool_size,
                                                    pool_maxsize=self.pool_size,
                                                    max_retries=quick)
            s.mount("https://", adapter)
            s.mount("http://", adapter)
            self._local.session = s
        return s

    def get(self, key: str, attempts: int = 8) -> bytes | None:
        url = f"{self.base}/{key}"
        for attempt in range(attempts):
            try:
                r = self._session().get(url, timeout=(30, 600))
                if r.status_code == 404:
                    return None
                r.raise_for_status()
                body = r.content
                expected = r.headers.get("Content-Length")
                if expected is not None and "Content-Encoding" not in r.headers \
                        and int(expected) != len(body):
                    raise IOError(f"short read: {len(body)} of {expected} bytes")
                with self._lock:
                    self.bytes += len(body)
                return body
            except (requests.RequestException, IOError) as exc:
                if attempt == attempts - 1:
                    raise
                wait = min(300, 5 * 2 ** attempt)
                print(f"    retry {attempt + 1}/{attempts - 1} for {key} in {wait}s: {exc}",
                      flush=True)
                time.sleep(wait)
        return None

    def note_missing(self, key: str) -> None:
        with self._lock:
            self.missing.append(key)


def chunk_keys(meta: dict, name: str) -> list[str]:
    za = meta["metadata"][f"{name}/.zarray"]
    sep = za.get("dimension_separator", ".")
    grid = [range(-(-s // c)) for s, c in zip(za["shape"], za["chunks"])]
    return [f"{name}/" + sep.join(map(str, idx)) for idx in itertools.product(*grid)]


def open_remote_arrays(remote: Remote, meta: dict, names: list[str],
                       threads: int) -> zarr.Group:
    """Pull every chunk of the named (small) arrays into memory and open them with zarr."""
    store = {".zmetadata": json.dumps(meta).encode()}
    for k, v in meta["metadata"].items():
        store[k] = json.dumps(v).encode()
    keys = [k for n in names for k in chunk_keys(meta, n)]
    with cf.ThreadPoolExecutor(threads) as ex:
        for k, blob in zip(keys, ex.map(remote.get, keys)):
            if blob is not None:
                store[k] = blob
    return zarr.open_consolidated(store, mode="r")


def fetch_block(remote: Remote, field: str, za: dict, codec, vc: int, sc: int,
                cols: np.ndarray, local_rows: np.ndarray, keep: int | None):
    """One source chunk -> the Ghana columns and selected rows of it."""
    sep = za.get("dimension_separator", ".")
    idx = [vc, sc] + [0] * (len(za["shape"]) - 2)
    key = f"calldata/{field}/" + sep.join(map(str, idx))
    dtype = np.dtype(za["dtype"])
    trailing = (keep,) if keep else ()

    blob = remote.get(key)
    if blob is None:
        # Zarr semantics: an absent chunk holds the fill value throughout.
        remote.note_missing(key)
        return field, np.full((len(local_rows), len(cols)) + trailing,
                              za["fill_value"], dtype=dtype)

    arr = np.frombuffer(codec.decode(blob), dtype=dtype).reshape(za["chunks"])
    sub = arr[local_rows][:, cols]
    if keep:
        sub = sub[..., :keep]
    return field, np.ascontiguousarray(sub)


# ---------------------------------------------------------------------------
# Validation against a local VCF
# ---------------------------------------------------------------------------

def validate(store_path: Path, vcf: Path, region: str) -> bool:
    import allel

    C.banner(f"Validation: {store_path.name} vs {vcf.name} ({region})")
    contig, start, end = parse_region(region)
    root = zarr.open_group(str(store_path), mode="r")
    if contig not in root:
        print(f"  {contig} is not in the store — nothing to compare.")
        return False
    g = root[contig]

    fields = ["samples", "variants/POS", "variants/FILTER_PASS", "variants/is_snp",
              "variants/numalt", "calldata/GT", "calldata/AD", "calldata/DP",
              "calldata/GQ"]
    print("  reading the VCF region (tabix + scikit-allel)...", flush=True)
    v = allel.read_vcf(str(vcf), region=region, fields=fields, alt_number=1)
    if v is None:
        print("  VCF region is empty.")
        return False
    keep = (v["variants/FILTER_PASS"] & v["variants/is_snp"]
            & (v["variants/numalt"] == 1))
    vpos = v["variants/POS"][keep]

    spos = g["variants/POS"][:]
    in_reg = np.ones(len(spos), dtype=bool)
    if start is not None:
        in_reg = (spos >= start) & (spos <= end)
    sidx = np.nonzero(in_reg)[0]
    print(f"  PASS biallelic SNPs: VCF {len(vpos):,}, store {len(sidx):,}")
    if len(sidx) == 0 or not np.array_equal(spos[sidx], vpos):
        print("  FAIL: site lists differ.")
        return False

    store_ids = np.asarray(g["samples"][:]).astype(str)
    vcf_ids = np.asarray(v["samples"]).astype(str)
    where = {s: i for i, s in enumerate(vcf_ids)}
    absent = [s for s in store_ids if s not in where]
    if absent:
        print(f"  FAIL: {len(absent)} store samples absent from the VCF, e.g. {absent[:3]}")
        return False
    order = np.array([where[s] for s in store_ids])

    ok = True
    lo, hi = int(sidx[0]), int(sidx[-1]) + 1
    for f, k in CALLDATA.items():
        a = np.asarray(v[f"calldata/{f}"][keep])[:, order]
        if k:
            a = a[..., :k]
        b = np.asarray(g[f"calldata/{f}"][lo:hi])
        if a.shape != b.shape:
            print(f"  {f}: FAIL shape {a.shape} vs {b.shape}")
            ok = False
            continue
        diff = int((a.astype(np.int64) != b.astype(np.int64)).sum())
        print(f"  {f}: {a.size:,} values compared, {diff:,} differ")
        ok &= diff == 0
    print("  PASS: store matches the VCF exactly." if ok else "  FAIL: see above.")
    return ok


# ---------------------------------------------------------------------------

def main() -> None:
    args = parse_args()
    C.banner("STEP 3a — fetch the Ghana callset from the Pf8 Zarr on Sanger")

    out = Path(args.out).resolve() if args.out else C.CALLSET_ZARR
    partial = out.with_name(out.name + ".partial")
    val_region = args.validate_region or args.region or DEFAULT_VALIDATE_REGION

    if args.validate_only:
        if not args.validate_vcf:
            raise SystemExit("--validate-only needs --validate-vcf.")
        raise SystemExit(0 if validate(out, Path(args.validate_vcf), val_region) else 1)

    if args.force:
        for p in (out, partial):
            if p.exists():
                print(f"--force: removing {p}")
                shutil.rmtree(p)

    if out.exists():
        attrs = zarr.open_group(str(out), mode="r").attrs.asdict()
        if attrs.get("pf8_fetch_complete"):
            print(f"{out} is already complete — nothing to fetch. --force rebuilds it.")
            if args.validate_vcf and not validate(out, Path(args.validate_vcf), val_region):
                raise SystemExit(1)
            return
        raise SystemExit(f"{out} exists but was not built by this script. "
                         f"Move it aside or pass --force.")

    remote = Remote(PF8_ZARR_URL, args.threads)
    meta = json.loads(remote.get(".zmetadata"))
    md = meta["metadata"]

    print("Reading sample IDs and variant metadata from the remote store...", flush=True)
    t = time.time()
    src = open_remote_arrays(remote, meta,
                             ["samples"] + [f"variants/{f}" for f in VARIANT_FIELDS],
                             args.threads)
    print(f"  {remote.bytes / 1e6:.0f} MB in {time.time() - t:.0f}s")

    # ---- samples ----------------------------------------------------------
    all_ids = np.asarray(src["samples"][:]).astype(str)
    wanted = [ln.strip() for ln in Path(args.samples).read_text().splitlines() if ln.strip()]
    lookup = {s: i for i, s in enumerate(all_ids)}
    absent = [s for s in wanted if s not in lookup]
    if absent:
        raise SystemExit(f"{len(absent)} IDs from {args.samples} are not in Pf8, "
                         f"e.g. {absent[:5]}. Check the sample list.")
    gi = np.unique(np.array([lookup[s] for s in wanted], dtype=np.int64))
    out_ids = all_ids[gi]
    n_s = len(gi)
    print(f"Samples: {n_s:,} of {len(all_ids):,} (from {Path(args.samples).name})")

    # ---- variants ---------------------------------------------------------
    chrom = np.asarray(src["variants/CHROM"][:]).astype(str)
    pos = np.asarray(src["variants/POS"][:])
    mask = (np.asarray(src["variants/FILTER_PASS"][:]).astype(bool)
            & np.asarray(src["variants/is_snp"][:]).astype(bool)
            & (np.asarray(src["variants/numalt"][:]) == 1))
    print(f"Variants: {len(chrom):,} in Pf8, {int(mask.sum()):,} PASS biallelic SNPs")
    if args.region:
        contig, start, end = parse_region(args.region)
        mask &= chrom == contig
        if start is not None:
            mask &= (pos >= start) & (pos <= end)
        print(f"  restricted to {args.region}: {int(mask.sum()):,}")

    sel = np.nonzero(mask)[0]
    if sel.size == 0:
        raise SystemExit("No variants selected.")
    sel_chrom = chrom[sel]
    del chrom, mask
    sel_pos = pos[sel].astype(np.int32)
    del pos
    ref = np.asarray(src["variants/REF"].oindex[sel]).astype(str)
    alt = np.asarray(src["variants/ALT"].oindex[sel, 0]).astype(str)
    del src

    contigs = list(dict.fromkeys(sel_chrom))
    out_row = np.empty(len(sel), dtype=np.int64)
    counts = {}
    for c in contigs:
        m = sel_chrom == c
        counts[c] = int(m.sum())
        out_row[m] = np.arange(counts[c])

    # ---- output store -----------------------------------------------------
    plan = {
        "source": PF8_ZARR_URL,
        "samples_file": str(Path(args.samples).resolve()),
        "n_samples": int(n_s),
        "samples_sha1": hashlib.sha1("\n".join(out_ids).encode()).hexdigest(),
        "filters": "FILTER_PASS & is_snp & numalt == 1"
                   + (f" & region {args.region}" if args.region else ""),
        "contig_counts": counts,
    }
    root = zarr.open_group(str(partial), mode="a")
    previous = root.attrs.get("plan")
    if previous is not None and previous != plan:
        raise SystemExit(f"{partial} was started with different samples or filters. "
                         f"Pass --force to discard it.")
    root.attrs["plan"] = plan

    comp = numcodecs.Blosc(cname="zstd", clevel=5, shuffle=numcodecs.Blosc.BITSHUFFLE)
    text = dict(dtype=object, object_codec=numcodecs.VLenUTF8(), compressor=comp)
    src_za = {f: md[f"calldata/{f}/.zarray"] for f in CALLDATA}
    for c in contigs:
        m = sel_chrom == c
        n = counts[c]
        g = root.require_group(c)
        g.array("samples", out_ids.astype(object), overwrite=True, **text)
        vchunk = (min(65536, n),)
        g.array("variants/CHROM", np.full(n, c, dtype=object), chunks=vchunk,
                overwrite=True, **text)
        g.array("variants/REF", ref[m].astype(object), chunks=vchunk, overwrite=True, **text)
        g.array("variants/ALT", alt[m].astype(object), chunks=vchunk, overwrite=True, **text)
        g.array("variants/POS", sel_pos[m], chunks=vchunk, compressor=comp, overwrite=True)
        g.array("variants/numalt", np.ones(n, dtype=np.int32), chunks=vchunk,
                compressor=comp, overwrite=True)
        g.array("variants/is_snp", np.ones(n, dtype=bool), chunks=vchunk,
                compressor=comp, overwrite=True)
        g.array("variants/FILTER_PASS", np.ones(n, dtype=bool), chunks=vchunk,
                compressor=comp, overwrite=True)
        for f, k in CALLDATA.items():
            tail = (k,) if k else ()
            g.require_dataset(f"calldata/{f}", shape=(n, n_s) + tail,
                              chunks=(min(OUT_VARIANT_CHUNK, n), OUT_SAMPLE_CHUNK) + tail,
                              dtype=np.dtype(src_za[f]["dtype"]), compressor=comp,
                              fill_value=-1)
    print(f"Writing to {partial}")
    for c in contigs:
        print(f"  {c:<14} {counts[c]:>9,} SNPs")

    # ---- chunk plan -------------------------------------------------------
    cs, scs = src_za["GT"]["chunks"][:2]
    for f, za in src_za.items():
        if za["chunks"][:2] != [cs, scs]:
            raise SystemExit(f"calldata/{f} is chunked differently from GT: {za['chunks']}")
    codecs = {f: numcodecs.get_codec(za["compressor"]) for f, za in src_za.items()}

    sc_of = gi // scs
    sample_chunks = []
    for sc in np.unique(sc_of):
        idx = np.nonzero(sc_of == sc)[0]
        sample_chunks.append((int(sc), gi[idx] - sc * scs, slice(int(idx[0]), int(idx[-1]) + 1)))

    vc_of = sel // cs
    vchunks = [int(v) for v in np.unique(vc_of)]
    done = set(root.attrs.get("done_vchunks", []))
    todo = [v for v in vchunks if v not in done]
    print(f"\nSource chunks: {len(vchunks)} variant x {len(sample_chunks)} sample "
          f"x {len(CALLDATA)} fields; {len(done)} variant chunks already done, "
          f"{len(todo)} to go. {args.threads} parallel downloads.\n", flush=True)

    # ---- fetch ------------------------------------------------------------
    t0, b0 = time.time(), remote.bytes
    with cf.ThreadPoolExecutor(args.threads) as pool:
        for i, vc in enumerate(todo, 1):
            t1, b1 = time.time(), remote.bytes
            lo, hi = np.searchsorted(vc_of, [vc, vc + 1])
            local = sel[lo:hi] - vc * cs

            bufs = {f: np.empty((len(local), n_s) + ((k,) if k else ()),
                                dtype=np.dtype(src_za[f]["dtype"]))
                    for f, k in CALLDATA.items()}
            futures = {}
            for f, k in CALLDATA.items():
                for sc, cols, osl in sample_chunks:
                    fut = pool.submit(fetch_block, remote, f, src_za[f], codecs[f],
                                      vc, sc, cols, local, k)
                    futures[fut] = osl
            for fut in cf.as_completed(futures):
                osl = futures.pop(fut)      # drop the reference so the block can be freed
                f, block = fut.result()
                bufs[f][:, osl] = block

            seg_chrom = sel_chrom[lo:hi]
            for c in dict.fromkeys(seg_chrom):
                rows = np.nonzero(seg_chrom == c)[0]
                a, b = int(rows[0]), int(rows[-1]) + 1
                r0 = int(out_row[lo + a])
                for f in CALLDATA:
                    root[c][f"calldata/{f}"][r0:r0 + (b - a)] = bufs[f][a:b]
            del bufs

            done.add(vc)
            root.attrs["done_vchunks"] = sorted(done)

            elapsed = time.time() - t0
            rate = (remote.bytes - b0) / max(elapsed, 1e-9) / 1e6
            eta = elapsed / i * (len(todo) - i)
            print(f"[{i:>3}/{len(todo)}] chunk {vc:>3} {', '.join(dict.fromkeys(seg_chrom))}: "
                  f"{len(local):>7,} SNPs, {(remote.bytes - b1) / 1e6:>6.0f} MB "
                  f"in {time.time() - t1:>4.0f}s | total {(remote.bytes - b0) / 1e9:6.1f} GB "
                  f"at {rate:4.1f} MB/s | ETA {eta / 3600:4.1f} h", flush=True)

    if remote.missing:
        print(f"\nNote: {len(remote.missing)} source chunks were absent and read as the "
              f"fill value, e.g. {remote.missing[:3]}")

    missing = set(vchunks) - done
    if missing:
        raise SystemExit(f"{len(missing)} variant chunks still missing: {sorted(missing)[:10]}")

    root.attrs["pf8_fetch_complete"] = True
    root.attrs["completed"] = time.strftime("%Y-%m-%d %H:%M:%S")
    del root.attrs["done_vchunks"]
    partial.rename(out)

    size = sum(p.stat().st_size for p in out.rglob("*") if p.is_file())
    C.banner("Done")
    print(f"Store  : {out}")
    print(f"Size   : {size / 1e9:.2f} GB on disk")
    print(f"Fetched: {(remote.bytes) / 1e9:.1f} GB in {(time.time() - t0) / 3600:.2f} h")
    print("Steps 3b and 4a will use this store directly; no VCF is needed.")

    if args.validate_vcf and not validate(out, Path(args.validate_vcf), val_region):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
