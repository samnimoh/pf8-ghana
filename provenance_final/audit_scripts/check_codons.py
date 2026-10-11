"""What residue would each non-PASS ALT encode? Reconstructs from the reference FASTA."""
import csv
COMP=str.maketrans("ACGT","TGCA")
B="TCAG"; AAs="FFLLSSSSYY**CC*WLLLLPPPPHHQQRRRRIIIMTTTTNNKKSSRRVVVVAAAADDEEGGGG"
CODE={}; k=0
for a in B:
    for b in B:
        for c in B: CODE[a+b+c]=AAs[k]; k+=1
ref={}
name=None; buf=[]
for line in open("/media/biodataA/pf8/gyadu/data/Pf3D7_reference.fasta"):
    if line.startswith(">"):
        if name: ref[name]="".join(buf)
        name=line[1:].split()[0]; buf=[]
    else: buf.append(line.strip())
if name: ref[name]="".join(buf)
CASES=[(675,1724975,"C",["G"]),(561,1725315,"A",["C","G","T"]),(553,1725339,"C",["T","A"])]
rows={int(r["codon"]):r for r in csv.DictReader(open("/media/biodataA/pf8/gyadu/results/codon_panel_residues.csv")) if r["gene"]=="pfk13"}
for cod,pos,refb,alts in CASES:
    r=rows[cod]; ps=[int(p) for p in r["positions"].split(";")]
    seq=ref[r["contig"]]
    bases=[seq[p-1].upper() for p in ps]
    assert seq[pos-1].upper()==refb, f"ref mismatch at {pos}: {seq[pos-1]} vs {refb}"
    cb=[b.translate(COMP) for b in bases]        # minus strand
    rc="".join(cb); raa=CODE[rc]
    print(f"\ncodon {cod}: positions {ps}  genomic {bases} -> codon {rc} = {raa} (CSV ref_residue {r['ref_residue']})")
    idx=ps.index(pos)
    for a in alts:
        mb=list(cb); mb[idx]=a.translate(COMP)
        mc="".join(mb); maa=CODE[mc]
        kind="SYNONYMOUS" if maa==raa else f"non-synonymous -> {maa}"
        print(f"   ALT {a} at {pos} (codon base {idx+1}) -> {mc} = {maa}   {kind}")
