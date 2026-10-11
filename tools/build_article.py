import re, os, sys, shutil, zipfile, html, posixpath
from urllib.parse import unquote, urlsplit
from xml.etree import ElementTree as ET
from pathlib import Path

SRC  = os.environ.get("ARTICLE_TEMPLATE", "supp")   # unzipped docx supplying styles/theme/fonts/media
OUT  = "article_pkg"
MD   = os.environ["ARTICLE_MD"]
DOCX = os.environ["ARTICLE_DOCX"]
REFS = os.environ.get("ARTICLE_REFS",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "references_apa.txt"))
_tmp = DOCX + ".tmp-build"


def inside(path, parent):
    return path == parent or parent in path.parents


def aliases(first, second):
    return first.resolve() == second.resolve() or (
        first.exists() and second.exists() and os.path.samefile(first, second))


def aliases_file_in(path, directory):
    if not path.is_file() or not directory.is_dir():
        return False
    inode = os.stat(path)
    for folder, _, filenames in os.walk(directory):
        for filename in filenames:
            candidate = os.stat(os.path.join(folder, filename))
            if (inode.st_dev, inode.st_ino) == (candidate.st_dev, candidate.st_ino):
                return True
    return False


# The work directory is disposable. Check both lexical and resolved paths before
# its removal: a symlink can otherwise hide a source/destination within it.
_work_path = Path(os.path.abspath(OUT))
_work_real = _work_path.resolve()
_source_real = Path(SRC).resolve()
if inside(_source_real, _work_real) or inside(_work_real, _source_real):
    sys.exit("unsafe build paths: ARTICLE_TEMPLATE overlaps the article_pkg work package")
if _work_path.is_symlink():
    sys.exit("unsafe build paths: article_pkg work package is a symlink")
for _name, _value in (("ARTICLE_DOCX", DOCX), ("temporary archive", _tmp),
                       ("ARTICLE_MD", MD), ("ARTICLE_REFS", REFS)):
    _path = Path(os.path.abspath(_value))
    if (inside(_path, _work_path) or inside(_path.resolve(), _work_real)
            or aliases_file_in(_path, _work_real)):
        sys.exit(f"unsafe build paths: {_name} is inside or aliases the article_pkg work package")
for _name, _value in (("ARTICLE_DOCX", DOCX), ("temporary archive", _tmp)):
    _path = Path(_value)
    if inside(_path.resolve(), _source_real) or aliases_file_in(_path, _source_real):
        sys.exit(f"unsafe build paths: {_name} is inside or aliases the ARTICLE_TEMPLATE")
    for _input_name, _input_value in (("ARTICLE_MD", MD), ("ARTICLE_REFS", REFS)):
        if aliases(_path, Path(_input_value)):
            sys.exit(f"unsafe build paths: {_name} aliases {_input_name}")
if aliases(Path(_tmp), Path(DOCX)):
    sys.exit("unsafe build paths: temporary archive aliases ARTICLE_DOCX")

for _p, _what in ((SRC, "ARTICLE_TEMPLATE (an unzipped .docx supplying styles/theme/fonts/media)"),
                  (MD,  "ARTICLE_MD"), (REFS, "ARTICLE_REFS / tools/references_apa.txt")):
    if not os.path.exists(_p):
        sys.exit(f"missing input: {_what} -> {_p}")

IMG = {  # our figure number -> (source media file, width_emu, height_emu)
 1: ("93b6764f7192ce47a8c3257fe6d80a68d84833ff.png", 5486400, 3657600),
 2: ("218857879d6287b87460540cea2d8ec053df7685.png", 5943600, 2250440),
 3: ("c8eab09bbe813dc6fe1001e38fae01b5b7482cd0.png", 5943600, 2600000),
}
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
DOCUMENT_RELS = [
    ("rId1", "styles", "styles.xml"),
    ("rId5", "settings", "settings.xml"),
    ("rId7", "theme", "theme/theme1.xml"),
    ("rId18", "fontTable", "fontTable.xml"),
    ("rId8", "image", "media/" + IMG[1][0]),
    ("rId10", "image", "media/" + IMG[2][0]),
    ("rId12", "image", "media/" + IMG[3][0]),
]
REQUIRED_SOURCE_PARTS = ["[Content_Types].xml", "_rels/.rels"] + [
    "word/" + target for _, _, target in DOCUMENT_RELS
]
REQUIRED_CONTENT_TYPES = {
    "word/document.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
    "word/styles.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml",
    "word/settings.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.settings+xml",
    "word/theme/theme1.xml": "application/vnd.openxmlformats-officedocument.theme+xml",
    "word/fontTable.xml": "application/vnd.openxmlformats-officedocument.wordprocessingml.fontTable+xml",
    **{"word/media/" + image[0]: "image/png" for image in IMG.values()},
}

# Check named assets before changing the working package. The input directory's
# existence alone does not establish that it can supply the article's parts.
for _part in REQUIRED_SOURCE_PARTS:
    _path = os.path.join(SRC, _part)
    if not os.path.isfile(_path) or os.path.getsize(_path) == 0:
        sys.exit(f"missing or empty ARTICLE_TEMPLATE part: {_part} -> {_path}")
    if _part.endswith((".xml", ".rels")):
        try:
            ET.parse(_path)
        except ET.ParseError as exc:
            sys.exit(f"invalid ARTICLE_TEMPLATE XML: {_part}: {exc}")


def validate_package(archive):
    """Check the final OPC graph, XML and type declarations before replacement.

    CRC checks cannot detect a relationship pointing to a missing package part.
    This checks all retained relationships, including font and metadata parts,
    and also verifies relationship IDs referenced by the XML that owns them.
    """
    entries = [n for n in archive.namelist() if not n.endswith("/")]
    names = set(entries)
    if len(names) != len(entries):
        raise ValueError("article package contains duplicate part names")
    required = set(REQUIRED_SOURCE_PARTS) | {"word/document.xml", "word/_rels/document.xml.rels"}
    absent = sorted(required - names)
    if absent:
        raise ValueError("article package is missing required parts: " + ", ".join(absent))
    trees = {}
    for name in names:
        if name.endswith((".xml", ".rels")):
            try:
                trees[name] = ET.fromstring(archive.read(name))
            except ET.ParseError as exc:
                raise ValueError(f"invalid package XML: {name}: {exc}") from exc

    ct = trees["[Content_Types].xml"]
    if ct.tag != "{" + CT_NS + "}Types":
        raise ValueError("invalid content-types root")
    defaults, overrides = {}, {}
    for item in ct:
        mime = item.get("ContentType", "")
        if not mime:
            raise ValueError("empty package content type")
        if item.tag == "{" + CT_NS + "}Default":
            extension = item.get("Extension", "").lower()
            if not extension or extension in defaults:
                raise ValueError("missing or duplicate content-type extension")
            defaults[extension] = mime
        elif item.tag == "{" + CT_NS + "}Override":
            part = unquote(item.get("PartName", ""))
            if not part.startswith("/") or part[1:] not in names:
                raise ValueError(f"content-type override refers to absent part: {part}")
            if part[1:] in overrides:
                raise ValueError(f"duplicate content-type override: {part}")
            overrides[part[1:]] = mime
        else:
            raise ValueError("invalid content-type declaration")
    for name in names - {"[Content_Types].xml"}:
        mime = overrides.get(name, defaults.get(name.rsplit(".", 1)[-1].lower()))
        if not mime:
            raise ValueError(f"package part has no content type: {name}")
        expected = REQUIRED_CONTENT_TYPES.get(name)
        if name.endswith(".rels"):
            expected = "application/vnd.openxmlformats-package.relationships+xml"
        if expected and mime != expected:
            raise ValueError(f"incorrect content type for {name}: {mime}")

    relationship_ids = {}
    package_document = False
    office_documents = 0
    for name in sorted(n for n in names if n.endswith(".rels")):
        if name == "_rels/.rels":
            owner, base = None, ""
        else:
            parent, filename = posixpath.split(name)
            if posixpath.basename(parent) != "_rels":
                raise ValueError(f"invalid relationship part path: {name}")
            base = posixpath.dirname(parent)
            owner = posixpath.join(base, filename[:-5])
            if owner not in names:
                raise ValueError(f"orphan relationship part: {name} (owner {owner} is absent)")
        tree = trees[name]
        if tree.tag != "{" + REL_NS + "}Relationships":
            raise ValueError(f"invalid relationships root: {name}")
        ids = set()
        for rel in tree:
            rid, kind, target = (rel.get(key, "") for key in ("Id", "Type", "Target"))
            if rel.tag != "{" + REL_NS + "}Relationship" or not rid or not kind or not target:
                raise ValueError(f"invalid relationship in {name}")
            if rid in ids:
                raise ValueError(f"duplicate relationship ID in {name}: {rid}")
            ids.add(rid)
            mode = rel.get("TargetMode", "Internal")
            if owner is None and kind == DOC_REL_NS + "/officeDocument":
                office_documents += 1
            if mode == "External":
                continue
            if mode != "Internal":
                raise ValueError(f"invalid relationship target mode in {name}: {mode}")
            uri = urlsplit(target)
            if uri.scheme or uri.netloc or uri.query:
                raise ValueError(f"invalid internal relationship target in {name}: {target}")
            path = unquote(uri.path)
            resolved = posixpath.normpath(path.lstrip("/") if path.startswith("/") else posixpath.join(base, path))
            if resolved.startswith("../") or resolved not in names:
                raise ValueError(f"missing relationship target: {name} {rid} -> {target}")
            if owner is None and kind == DOC_REL_NS + "/officeDocument" and resolved == "word/document.xml":
                package_document = True
        relationship_ids[owner] = ids
    if office_documents != 1 or not package_document:
        raise ValueError("package root does not reference word/document.xml as its exactly one office document")
    for name, tree in trees.items():
        if name.endswith(".rels") or name == "[Content_Types].xml":
            continue
        for element in tree.iter():
            for key, value in element.attrib.items():
                if key in {"{" + DOC_REL_NS + "}" + suffix for suffix in ("id", "embed", "link")}:
                    if value not in relationship_ids.get(name, set()):
                        raise ValueError(f"unresolved relationship ID in {name}: {value}")

FIGCAP = {
 1: "Sampling locations on the Ghana agro-ecological zone layer. Each point is one administrative-region centroid; colour gives the agro-ecological zone to which isolates from that region were assigned.",
 2: "UMAP, t-SNE and PCoA of the 1,900-isolate genotype-distance submatrix, coloured by agro-ecological zone. No zone forms a distinct cluster under any of the three methods; all silhouette coefficients are negative.",
 3: "BayPass XtX genome scan on the 3,916-SNP matrix. Left: the observed XtX distribution against the pseudo-observed neutral distribution, with the calibrated 0.999-quantile threshold at 10.840. Right: XtX along the genome.",
}

def esc(s): return s.replace("&","&amp;").replace("<","&lt;").replace(">","&gt;")

TOK = re.compile(r'(\*\*.+?\*\*|\*[^*\n]+?\*|~[A-Za-z]{1,4}~)')
def runs(text, base="", extra=""):
    out=[]
    for part in TOK.split(text):
        if not part: continue
        if part.startswith("**") and part.endswith("**"):
            out.append((part[2:-2], base+"b"))
        elif part.startswith("~") and part.endswith("~") and len(part)>2:
            out.append((part[1:-1], base+"s"))
        elif part.startswith("*") and part.endswith("*") and len(part)>2:
            out.append((part[1:-1], base+"i"))
        else:
            out.append((part, base))
    xml=""
    for t,f in out:
        bits=""
        if "b" in f: bits+="<w:b/><w:bCs/>"
        if "i" in f: bits+="<w:i/><w:iCs/>"
        if "s" in f: bits+='<w:vertAlign w:val="subscript"/>'
        allbits = extra + bits
        rpr=f"<w:rPr>{allbits}</w:rPr>" if allbits else ""
        xml+=f'<w:r>{rpr}<w:t xml:space="preserve">{esc(t)}</w:t></w:r>'
    return xml

def para(text, style=None, after=160, ind=None, size=None, italic=False, align=None):
    pr=""
    if style: pr+=f'<w:pStyle w:val="{style}"/>'
    if align: pr+=f'<w:jc w:val="{align}"/>'
    pr+=f'<w:spacing w:after="{after}" w:line="276"/>'
    if ind: pr+=f'<w:ind w:left="{ind[0]}" w:hanging="{ind[1]}"/>'
    body=runs(text, "i" if italic else "",
              extra=(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>' if size else ""))
    return f'<w:p><w:pPr>{pr}</w:pPr>{body}</w:p>'

def figure(n, rid):
    f, cx, cy = IMG[n]
    drawing=(f'<w:p><w:pPr><w:jc w:val="center"/><w:spacing w:after="80" w:before="200"/></w:pPr><w:r><w:drawing>'
      f'<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>'
      f'<wp:docPr id="{100+n}" name="Figure {n}"/><a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
      f'<a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">'
      f'<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">'
      f'<pic:nvPicPr><pic:cNvPr id="{100+n}" name="Figure {n}"/><pic:cNvPicPr/></pic:nvPicPr>'
      f'<pic:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>'
      f'<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
      f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr></pic:pic>'
      f'</a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>')
    cap=para(f"**Fig. {n}** {FIGCAP[n]}", after=240, size=18, italic=False)
    return drawing+cap

def table(caption, header, rows, widths):
    tw="".join(f'<w:gridCol w:w="{w}"/>' for w in widths)
    def cell(t,w,bold=False,size=18):
        body=runs(t, base=("b" if bold else ""),
                  extra=f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
        return (f'<w:tc><w:tcPr><w:tcW w:type="dxa" w:w="{w}"/>'
                f'<w:tcMar><w:top w:type="dxa" w:w="60"/><w:left w:type="dxa" w:w="90"/>'
                f'<w:bottom w:type="dxa" w:w="60"/><w:right w:type="dxa" w:w="90"/></w:tcMar></w:tcPr>'
                f'<w:p><w:pPr><w:spacing w:after="0" w:line="240"/></w:pPr>{body}</w:p></w:tc>')
    out=para(caption, after=80, size=18)
    out+=('<w:tbl><w:tblPr><w:tblStyle w:val="TableGrid"/><w:tblW w:type="auto" w:w="0"/>'
          '<w:tblBorders>'
          '<w:top w:val="single" w:sz="6" w:color="999999"/><w:bottom w:val="single" w:sz="6" w:color="999999"/>'
          '<w:insideH w:val="single" w:sz="4" w:color="CCCCCC"/></w:tblBorders></w:tblPr>'
          f'<w:tblGrid>{tw}</w:tblGrid>')
    out+='<w:tr>'+''.join(cell(h,w,bold=True) for h,w in zip(header,widths))+'</w:tr>'
    for r in rows:
        out+='<w:tr>'+''.join(cell(str(c),w) for c,w in zip(r,widths))+'</w:tr>'
    out+='</w:tbl>'+para("", after=200)
    return out

# ---------------- tables ----------------
T1 = table("**Table 1** Composition of the analysis set, with the sequencing study, administrative region and collection period that accompany each agro-ecological zone. Zone is very nearly a relabelling of region and study: three of the four zones draw on a single administrative region, and one on a single study. The final column is measured on the pre-filter quality-control cohort of 4,905 isolates, not on the analysis set: every analysed isolate satisfies F~ws~ \u2265 0.95 by construction, so its polyclonal fraction is zero. QC-cohort denominators are given in the column.",
 ["Agro-ecological zone","Isolates","Administrative region(s)","No. studies","Dominant study (share)","Collection years","Polyclonal fraction (QC cohort)"],
 [["Guinea savanna","1,334","Upper East (1,334)","6","1168-PF-GH-AMENGA-ETEGO-SM (74%)","2009–2019","0.597 (n = 3,605)"],
  ["Deciduous forest","337","Ashanti (157), Central (125), Eastern (34), Volta (21)","5","1200-PF-GH-MAIGA-SM (47%)","2013–2021","0.539 (n = 815)"],
  ["Coastal savanna","204","Greater Accra (204)","2","1241-PF-GH-ANINAGYEI (87%)","2016–2018","0.444 (n = 435)"],
  ["Transitional zone","25","Brong Ahafo (25)","1","1083-PF-GH-CONWAY (100%)","2011–2013","0.500 (n = 50)"]],
 [1450,750,2250,620,2000,1050,1180])

T2 = table("**Table 2** Pairwise Hudson F~ST~ between agro-ecological zones on 3,916 SNPs and 1,900 isolates, with block-jackknife 95% confidence intervals. Five of the six intervals exclude zero.",
 ["Zone pair","n","n","F~ST~","95% CI","Excludes zero"],
 [["Coastal savanna × Guinea savanna","204","1,334","0.00232","0.00128 – 0.00336","Yes"],
  ["Coastal savanna × Transitional zone","204","25","0.00158","0.00006 – 0.00309","Yes"],
  ["Deciduous forest × Transitional zone","337","25","0.00158","0.00017 – 0.00298","Yes"],
  ["Deciduous forest × Guinea savanna","337","1,334","0.00134","0.00088 – 0.00180","Yes"],
  ["Guinea savanna × Transitional zone","1,334","25","0.00047","−0.00083 – 0.00178","No"],
  ["Coastal savanna × Deciduous forest","204","337","0.00045","0.00019 – 0.00070","Yes"]],
 [3100,600,600,1000,1900,1100])

T3 = table("**Table 3** Resistance-marker frequencies overall and by agro-ecological zone. Denominators are isolates called at that codon or, for haplotypes, isolates called at every constituent codon. The chi-square column tests heterogeneity across the four zones.",
 ["Marker","Overall","n","Coastal savanna","Deciduous forest","Guinea savanna","Transitional","χ² p"],
 [["*pfdhfr* N51I","0.786","1,891","—","—","—","—","2.43 × 10⁻⁴"],
  ["*pfdhfr* C59R","0.886","1,888","—","—","—","—","4.80 × 10⁻⁵"],
  ["*pfdhfr* S108N","0.908","1,889","—","—","—","—","9.40 × 10⁻⁷"],
  ["*pfdhfr* I164L","0.000","1,898","—","—","—","—","—"],
  ["*pfdhfr* IRN triple","0.771","1,876","0.867","0.788","0.750","0.880","—"],
  ["*pfdhfr* IRNL quadruple","0.000","1,874","0.000","0.000","0.000","0.000","—"],
  ["*pfdhps* G437","0.897","1,892","0.941","0.964","0.875","0.800","1.17 × 10⁻⁶"],
  ["*pfdhps* S436A","0.541","1,884","—","—","—","—","1.61 × 10⁻³"],
  ["*pfdhps* K540E","0.0095","1,895","—","—","—","—","0.661"],
  ["*pfdhps* A581G","0.0138","1,890","—","—","—","—","8.02 × 10⁻⁴"],
  ["*pfdhps* A613S","0.108","1,884","—","—","—","—","0.113"],
  ["*pfdhps* GE double","0.0095","1,888","0.005","0.006","0.011","0.000","—"],
  ["*pfcrt* K76T","0.071","1,874","—","—","—","—","0.037"],
  ["*pfcrt* CVIET haplotype","0.071","1,873","0.054","0.104","0.064","0.125","—"],
  ["*pfmdr1* N86Y","0.088","1,887","—","—","—","—","0.029"],
  ["*pfmdr1* Y184F","0.677","1,858","—","—","—","—","0.364"],
  ["*pfmdr1* D1246Y","0.011","1,866","—","—","—","—","0.262"],
  ["*pfmdr2* I492V","0.549","1,885","—","—","—","—","0.020"],
  ["*pfaat1* S258L","0.609","1,896","0.824","—","0.544","—","1.89 × 10⁻¹⁸"],
  ["*pfk13* (23 codons)","0.000","1,845–1,876","0.000","0.000","0.000","0.000","—"]],
 [2200,900,900,1200,1300,1200,1100,1200])

T4 = table("**Table 4** Threshold sensitivity of the two headline spatial results. The maximum pairwise F~ST~ is stable across all six scenarios; the distance effect clears p = 0.05 in only two of them.",
 ["Scenario","Isolates","SNPs","Max F~ST~","Mantel r","Mantel p","p < 0.05"],
 [["Baseline (F~ws~ ≥ 0.95, MAF ≥ 0.05)","1,900","3,916","0.00232","0.427","0.0252","Yes"],
  ["F~ws~ ≥ 0.90","2,196","3,629","0.00240","0.318","0.0874","No"],
  ["F~ws~ ≥ 0.80","2,746","3,496","0.00255","0.256","0.1687","No"],
  ["No F~ws~ filter","4,403","3,275","0.00254","0.245","0.1792","No"],
  ["MAF ≥ 0.01","1,900","10,876","0.00204","0.432","0.0617","No"],
  ["MAF ≥ 0.02","1,900","6,852","0.00217","0.434","0.0467","Yes"]],
 [2600,1000,1000,1100,1000,1000,900])

PLACE = {"[[FIG1]]": figure(1,"rId8"), "[[FIG2]]": figure(2,"rId10"), "[[FIG3]]": figure(3,"rId12"),
         "[[TABLE1]]": T1, "[[TABLE2]]": T2, "[[TABLE3]]": T3, "[[TABLE4]]": T4}

# ---------------- markdown -> body ----------------
body=[]
for raw in open(MD, encoding="utf-8").read().split("\n"):
    line=raw.rstrip()
    if line.strip() in PLACE:
        body.append(PLACE[line.strip()]); continue
    if not line.strip():
        continue
    if line.startswith("### "):
        body.append(para(line[4:], style="Heading2", after=120)); continue
    if line.startswith("## "):
        body.append(para(line[3:], style="Heading1", after=160)); continue
    if line.startswith("# "):
        body.append(para(line[2:], style="Heading1", after=240)); continue
    body.append(para(line))

# references
body.append(para("References", style="Heading1", after=160))
for r in open(REFS, encoding="utf-8"):
    r=r.strip()
    if not r: continue
    r=r.replace("{i}","*").replace("{/i}","*").replace("{s}","~").replace("{/s}","~")
    body.append(para(r, after=120, ind=(400,400), size=19))

DOC=('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
 '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main" '
 'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
 'xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing" '
 'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
 '<w:body>' + "".join(body) +
 '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
 '<w:pgMar w:top="1134" w:right="1134" w:bottom="1134" w:left="1134" w:header="567" w:footer="567"/>'
 '</w:sectPr></w:body></w:document>')

# ---------------- package ----------------
if os.path.exists(OUT): shutil.rmtree(OUT)
shutil.copytree(SRC, OUT)
for f in os.listdir(f"{OUT}/word/media"):
    if f not in [v[0] for v in IMG.values()]: os.remove(f"{OUT}/word/media/{f}")
open(f"{OUT}/word/document.xml","w",encoding="utf-8").write(DOC)
rels=('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
      f'<Relationships xmlns="{REL_NS}">' + ''.join(
          f'<Relationship Id="{rid}" Type="{DOC_REL_NS}/{kind}" Target="{target}"/>'
          for rid, kind, target in DOCUMENT_RELS) + '</Relationships>')
open(f"{OUT}/word/_rels/document.xml.rels","w",encoding="utf-8").write(rels)
for junk in ("footnotes.xml","endnotes.xml","numbering.xml","footer1.xml"):
    p=f"{OUT}/word/{junk}"
    if os.path.exists(p): os.remove(p)
    p=f"{OUT}/word/_rels/{junk}.rels"
    if os.path.exists(p): os.remove(p)
ct_path = f"{OUT}/[Content_Types].xml"
ct_tree = ET.parse(ct_path)
discarded = {"/word/" + part for part in ("footnotes.xml", "endnotes.xml", "numbering.xml", "footer1.xml")}
for declaration in list(ct_tree.getroot()):
    if declaration.tag == "{" + CT_NS + "}Override" and declaration.get("PartName") in discarded:
        ct_tree.getroot().remove(declaration)
ET.register_namespace("", CT_NS)
ct_tree.write(ct_path, encoding="utf-8", xml_declaration=True)

import xml.dom.minidom as mdom
mdom.parse(f"{OUT}/word/document.xml")
print("document.xml well-formed")
# Build to a sibling temp file and swap it in only once it is complete, so a
# failure part-way through can never destroy an existing deliverable.
try:
    with zipfile.ZipFile(_tmp, "w", zipfile.ZIP_DEFLATED) as zf:
        for root, _, files in os.walk(OUT):
            for f in files:
                full = os.path.join(root, f)
                zf.write(full, os.path.relpath(full, OUT))
    with open(_tmp, "rb") as fh:
        os.fsync(fh.fileno())
    with zipfile.ZipFile(_tmp) as zf:
        if zf.testzip() is not None:
            raise RuntimeError("archive failed its own integrity check")
        validate_package(zf)
    os.replace(_tmp, DOCX)                      # atomic on the same filesystem
except BaseException:
    if os.path.exists(_tmp): os.remove(_tmp)    # leave any existing DOCX untouched
    raise
print(f"wrote {DOCX}  {os.path.getsize(DOCX)/1e6:.2f} MB")
