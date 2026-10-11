#!/usr/bin/env python3
"""Isolated Pf8 audit. Reproduce original filtering before comparing alternatives.

Run in the server's spatial environment. Original pipeline outputs are read only.
"""
import argparse
import hashlib
import itertools
import json
import os
from pathlib import Path
import sys
import time

import allel
import numpy as np
import pandas as pd
from pyproj import Geod
import zarr

p = argparse.ArgumentParser()
p.add_argument('--root', default='/media/biodataA/pf8/gyadu')
p.add_argument('--out', default='/media/biodataA/pf8/gyadu/evaluation_20261009')
a = p.parse_args()
ROOT, OUT = Path(a.root), Path(a.out)
OUT.mkdir(parents=True, exist_ok=True)
sys.path.insert(0, str(ROOT / 'scripts'))
import callset_io as cio

def dump(name, obj):
    (OUT / 'results' / name).write_text(json.dumps(obj, indent=2, allow_nan=False))

def acount(h, labels):
    return {z: np.stack(((h[:, labels == z] == 0).sum(1),
                          (h[:, labels == z] == 1).sum(1)), axis=1)
            for z in sorted(pd.unique(labels))}

def fst_matrix(h, meta, column):
    counts = meta[column].value_counts()
    pops = sorted(counts[counts >= 10].index)
    labels = meta[column].to_numpy()
    ac = acount(h, labels)
    mat = np.zeros((len(pops), len(pops)))
    rows = []
    blen = min(2000, max(10, len(h) // 20))
    for i, j in itertools.combinations(range(len(pops)), 2):
        num, den = allel.hudson_fst(ac[pops[i]], ac[pops[j]])
        good = np.isfinite(num) & np.isfinite(den)
        value = float(num[good].sum() / den[good].sum())
        _, se, _, _ = allel.average_hudson_fst(ac[pops[i]], ac[pops[j]], blen)
        mat[i, j] = mat[j, i] = value
        rows.append(dict(pop_a=pops[i], pop_b=pops[j], n_a=int(counts[pops[i]]),
                         n_b=int(counts[pops[j]]), fst=value, jackknife_se=float(se),
                         ci95_low=value-1.96*se, ci95_high=value+1.96*se))
    return pops, mat, pd.DataFrame(rows), ac

def mantel_exact(fst, geo, clip=False):
    """All label permutations, including identity, counted exactly once."""
    n = len(fst)
    tri = np.triu_indices(n, 1)
    x = fst / (1 - fst)
    if clip:
        x = np.maximum(x, 0)
    y = np.log(geo, out=np.zeros_like(geo), where=geo > 0)[tri]
    y = (y - y.mean()) / np.linalg.norm(y - y.mean())
    observed = x[tri]
    observed = (observed-observed.mean()) / np.linalg.norm(observed-observed.mean())
    corr = float(observed @ y)
    count = total = 0
    for order in itertools.permutations(range(n)):
        v = x[np.ix_(order, order)][tri]
        v = (v-v.mean()) / np.linalg.norm(v-v.mean())
        count += float(v @ y) >= corr - 1e-12
        total += 1
    return dict(r=corr, p=count/total, n_populations=n, n_permutations=total,
                n_extreme=count, negative_pairs=int((fst[tri] < 0).sum()), clipped=clip)

def geography(meta, column, pops):
    points = meta.groupby(column)[['Admin level 1 longitude', 'Admin level 1 latitude']].mean().loc[pops]
    geod = Geod(ellps='WGS84')
    geo = np.zeros((len(pops), len(pops)))
    for i, j in itertools.combinations(range(len(pops)), 2):
        x, y = points.iloc[i], points.iloc[j]
        geo[i, j] = geo[j, i] = geod.inv(x.iloc[0], x.iloc[1], y.iloc[0], y.iloc[1])[2]/1000
    return geo

q = pd.read_csv(ROOT/'results/sample_qc_full.csv')
release = pd.read_csv(OUT/'inputs/Pf8_fws.tsv', sep='\t').rename(columns={'Fws':'Fws_release'})
q = q.merge(release, on='Sample', how='left', validate='one_to_one')
assert q.Fws_release.notna().all()
q.to_csv(OUT/'results/qc_with_release_fws.csv', index=False)
fws = dict(n=len(q), correlation=float(q.Fws.corr(q.Fws_release)),
           median_pipeline=float(q.Fws.median()), median_release=float(q.Fws_release.median()),
           pipeline_pass=int((q.Fws >= .95).sum()), release_pass=int((q.Fws_release >= .95).sum()),
           pipeline_only=int(((q.Fws >= .95)&(q.Fws_release < .95)).sum()),
           release_only=int(((q.Fws < .95)&(q.Fws_release >= .95)).sum()))
dump('fws_comparison.json', fws)
print('Fws comparison', fws, flush=True)

# Recompute representatives among QC-eligible members to test selection ordering.
other_ok = ~(q.fail_call_rate | q.fail_call_rate_outlier | q.fail_het_outlier)
eligible = other_ok & (q.Fws >= .95)
ordered = q.loc[eligible].sort_values(['clonal_group','call_rate','Fws','Sample'],
                                    ascending=[True,False,False,True])
correct_reps = q.Sample.isin(ordered.drop_duplicates('clonal_group').Sample)
original_ok = q.qc_pass.to_numpy()
dump('clonal_order_audit.json', dict(original_qc=int(original_ok.sum()),
       eligible_first_qc=int((eligible & correct_reps).sum()),
       recovered_samples=q.loc[eligible & correct_reps & ~q.qc_pass, 'Sample'].tolist()))

root = zarr.open_group(str(ROOT/'interim/pf8_ghana.zarr'), mode='r')
ids = cio.samples(root)
lookup = {s:i for i,s in enumerate(ids)}
cols = np.array([lookup[s] for s in q.Sample.astype(str)])
variants = cio.variant_table(root)
assert variants.filter_pass.all() and variants.is_snp.all() and (variants.numalt == 1).all()
nvar, nsamp = len(variants), len(q)
print('Reading', nvar, 'variants and', nsamp, 'QC-entry samples', flush=True)
# Three compact haploid matrices use ~32 GB, avoiding the original full-callset load.
major = np.empty((nvar, nsamp), dtype=np.int8)
strict = np.empty_like(major)
missing = np.empty_like(major)
total_calls = retained_calls = added_calls = mixed_added = partial_calls = 0
balance_added = []
started = time.time()
for group, part in variants.groupby('group', sort=False):
    g = root[group]
    for first in range(0, len(part), 10000):
        segment = part.iloc[first:first+10000]
        rows = segment.local.to_numpy()
        glob = segment['global'].to_numpy()
        gt = g['calldata/GT'].get_orthogonal_selection((rows, cols, slice(None)))
        dp = g['calldata/DP'].get_orthogonal_selection((rows, cols))
        gq = g['calldata/GQ'].get_orthogonal_selection((rows, cols))
        called = (gt >= 0).all(2) & (dp >= 5)
        partial_calls += int(((gt >= 0).any(2) & ~(gt >= 0).all(2)).sum())
        mixed = called & (gt[:,:,0] != gt[:,:,1])
        h = gt[:,:,0].copy()
        h[~called] = -1
        hm = h.copy()
        hm[mixed] = -1
        ad = g['calldata/AD'].get_orthogonal_selection((rows, cols, slice(None))).astype(np.int32)
        ad = np.maximum(ad, 0)
        h[mixed & (ad[:,:,0] > ad[:,:,1])] = 0
        h[mixed & (ad[:,:,1] > ad[:,:,0])] = 1
        h[mixed & (ad[:,:,0] == ad[:,:,1])] = -1
        hs = h.copy()
        hs[gq < 20] = -1
        major[glob], strict[glob], missing[glob] = h, hs, hm
        # Diagnostics use the original final cohort, independently of changed sites.
        b = original_ok
        extra = (h[:,b] >= 0) & (hs[:,b] < 0)
        added_calls += int(extra.sum())
        mixed_added += int((extra & mixed[:,b]).sum())
        retained_calls += int((hs[:,b] >= 0).sum())
        total_calls += int((h[:,b] >= 0).sum())
        if extra.any():
            ad_b = ad[:,b]
            dep = ad_b.sum(2)
            bal = np.divide(ad_b.max(2), np.maximum(dep,1))
            vals = bal[extra]
            # Exact aggregate counts; keep fixed small histogram for the genome-wide distribution.
            balance_added.append(np.histogram(vals,bins=np.linspace(0,1,21))[0])
    print(group, 'elapsed', round(time.time()-started,1), 's', flush=True)
dump('gq_call_audit.json', dict(dp_only_calls=total_calls, gq20_calls=retained_calls,
      additional_calls=added_calls, additional_mixed_calls=mixed_added,
      partial_calls=partial_calls, major_balance_bin_edges=np.linspace(0,1,21).tolist(),
      additional_call_balance_histogram=np.sum(balance_added,axis=0).tolist(),
      shared_call_disagreements=0,
      shared_call_agreement_is_guaranteed='Masks retain identical upstream GT; no independent accuracy estimate'))

scenarios = [
    ('baseline', original_ok, major, .05),
    ('fws090', (other_ok & ~q.fail_clonal & (q.Fws >= .90)).to_numpy(), major, .05),
    ('fws080', (other_ok & ~q.fail_clonal & (q.Fws >= .80)).to_numpy(), major, .05),
    ('maf001', original_ok, major, .01),
    ('gq20', original_ok, strict, .05),
    ('mixed_missing', original_ok, missing, .05),
    ('release_fws095', (other_ok & ~q.fail_clonal & (q.Fws_release >= .95)).to_numpy(), major, .05),
    ('eligible_clones', (eligible & correct_reps).to_numpy(), major, .05),
]
summary=[]
baseline_h=baseline_meta=baseline_var=None
for name, keep, source, minmaf in scenarios:
    folder=OUT/name
    for d in ['interim','results','results/baypass','results/admixture','figures','logs']:
        (folder/d).mkdir(parents=True,exist_ok=True)
    meta=q.loc[keep].reset_index(drop=True)
    h=source[:,keep]
    vk=(h<0).mean(1)<=.1
    h=h[vk]
    var=variants.loc[vk].reset_index(drop=True)
    sk=(h<0).mean(0)<=.2
    h=h[:,sk]
    meta=meta.loc[sk].reset_index(drop=True)
    alt=(h==1).sum(1); total=(h>=0).sum(1)
    maf=np.minimum(alt,total-alt)/np.maximum(total,1)
    mk=maf>=minmaf
    h=h[mk];var=var.loc[mk].reset_index(drop=True)
    sample_ids=meta.Sample.astype(str).to_numpy(dtype='U64')
    np.savez_compressed(folder/'interim/ghana_core_snps.npz',
                        gt=np.repeat(h[:,:,None],2,axis=2),
                        chrom=var.chrom.to_numpy(dtype='U32'),pos=var.pos.to_numpy(),
                        ref=var.ref.to_numpy(dtype='U1'),alt=var.alt.to_numpy(dtype='U1'),samples=sample_ids)
    meta.to_csv(folder/'interim/analysis_samples.csv',index=False)
    pops,fst,pairs,ac=fst_matrix(h,meta,'zone')
    pairs.to_csv(folder/'results/fst_pairwise.csv',index=False)
    pd.DataFrame(fst,index=pops,columns=pops).to_csv(folder/'results/fst_matrix.csv')
    np.save(folder/'results/fst_matrix.npy',fst)
    np.savez_compressed(folder/'interim/allele_counts_by_zone.npz',
                        zones=np.array(pops,dtype='U64'),chrom=var.chrom.to_numpy(dtype='U32'),
                        pos=var.pos.to_numpy(),**{'ac__'+'_'.join(z.split()):ac[z] for z in pops})
    (folder/'interim/zone_order.txt').write_text('\n'.join(pops)+'\n')
    record=dict(scenario=name,n_qc=int(keep.sum()),n_samples=len(meta),n_snps=len(var),
                missing_fraction=float((h<0).mean()),max_fst=float(fst.max()),
                n_ci_spanning_zero=int(((pairs.ci95_low<=0)&(pairs.ci95_high>=0)).sum()),
                samples_per_zone={z:int(n) for z,n in meta.zone.value_counts().items()})
    summary.append(record)
    print(name, record, flush=True)
    if name=='baseline':
        old=np.load(ROOT/'interim/ghana_core_snps.npz',allow_pickle=True)
        assert np.array_equal(sample_ids,old['samples'].astype(str))
        assert np.array_equal(var.pos.to_numpy(),old['pos'])
        assert np.array_equal(var.chrom.to_numpy(),old['chrom'])
        assert np.array_equal(h,old['gt'][:,:,0])
        assert np.array_equal(old['gt'][:,:,0],old['gt'][:,:,1])
        dump('baseline_reproduction.json',dict(exact_samples=True,exact_positions=True,exact_genotypes=True,
             n_snps=len(h),n_samples=h.shape[1]))
        baseline_h,baseline_meta,baseline_var=h.copy(),meta.copy(),var.copy()
        for column in ['zone','Admin level 1']:
            rp,rm,rr,_=fst_matrix(h,meta,column)
            geo=geography(meta,column,rp)
            label='zone' if column=='zone' else 'region'
            results=[]
            for clip in [False,True]:
                entry=mantel_exact(rm,geo,clip)
                entry.update(level=label,populations=rp)
                results.append(entry)
            if label=='region':
                for i,pop in enumerate(rp):
                    sub=np.arange(len(rp))!=i
                    entry=mantel_exact(rm[np.ix_(sub,sub)],geo[np.ix_(sub,sub)],False)
                    entry.update(level=label,omitted=pop)
                    results.append(entry)
                rr.to_csv(OUT/'results/fst_region_pairwise.csv',index=False)
            dump('mantel_exact_'+label+'.json',results)
    del h

# Temporal sensitivity fixes the baseline SNP ascertainment and sample QC.
take=pd.to_numeric(baseline_meta.Year,errors='coerce').to_numpy()==2018
meta=baseline_meta.loc[take].reset_index(drop=True)
h=baseline_h[:,take]
pops,fst,pairs,ac=fst_matrix(h,meta,'zone')
pairs.to_csv(OUT/'results/fst_2018_fixed_sites.csv',index=False)
dump('single_year_2018.json',dict(n_samples=len(meta),n_snps=len(h),
     samples_per_zone={z:int(n) for z,n in meta.zone.value_counts().items()},max_fst=float(fst.max()),
     interpretation='Baseline sites and QC held fixed; collection year restricted to 2018'))
pd.DataFrame([{k:v for k,v in row.items() if k!='samples_per_zone'} for row in summary]).to_csv(
    OUT/'results/sensitivity_summary.csv',index=False)
dump('sensitivity_summary.json',summary)
# Tables for pre/post filtering and time confounding.
q.groupby(['zone','Year']).agg(n=('Sample','size'),median_fws=('Fws','median'),
                            median_release_fws=('Fws_release','median')).reset_index().to_csv(
    OUT/'results/fws_by_zone_year.csv',index=False)
print('AUDIT COMPLETE',round(time.time()-started,1),'s',flush=True)
