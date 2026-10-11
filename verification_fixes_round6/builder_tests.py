"""Exercise article-package safeguards on scratch copies, never deliverables."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import zipfile
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
BUILDER = ROOT / "tools/build_article.py"
EVIDENCE = Path(__file__).with_name("builder_test_results.json")
SCRATCH = Path(tempfile.mkdtemp(prefix="pf8_builder_fixes_", dir="/private/tmp"))
ARTICLE = ROOT / "article/Pf8_Ghana_article.docx"
TEMPLATE = ROOT / "article/Additional_file_1.docx"
REL_NS = "http://schemas.openxmlformats.org/package/2006/relationships"
DOC_REL_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
CT_NS = "http://schemas.openxmlformats.org/package/2006/content-types"
FIGURES = ["93b6764f7192ce47a8c3257fe6d80a68d84833ff.png",
           "218857879d6287b87460540cea2d8ec053df7685.png",
           "c8eab09bbe813dc6fe1001e38fae01b5b7482cd0.png"]


def sha(data):
    return hashlib.sha256(data).hexdigest()


article_bytes = ARTICLE.read_bytes()
template_bytes = TEMPLATE.read_bytes()
builder_before = sha(BUILDER.read_bytes())
with zipfile.ZipFile(ARTICLE) as z:
    article_xml = z.read("word/document.xml")
baseline = SCRATCH / "baseline_template"
baseline.mkdir()
with zipfile.ZipFile(TEMPLATE) as z:
    z.extractall(baseline)

wrapper = SCRATCH / "builder_fault_driver.py"
wrapper.write_text('''import os, runpy, sys, zipfile
phase=sys.argv[1]
if phase=="archive_write":
    saved=zipfile.ZipFile.write
    n=[0]
    def fail(z,*a,**kw):
        n[0]+=1
        if n[0]==5: raise OSError("synthetic fifth archive write failure")
        return saved(z,*a,**kw)
    zipfile.ZipFile.write=fail
elif phase=="integrity_check":
    zipfile.ZipFile.testzip=lambda z: "synthetic_corrupt_member"
elif phase=="fsync":
    def fail(*a,**kw): raise OSError("synthetic fsync failure")
    os.fsync=fail
elif phase=="replace":
    def fail(*a,**kw): raise OSError("synthetic atomic replacement failure")
    os.replace=fail
elif phase=="semantic_missing_image":
    saved=zipfile.ZipFile.write
    def skip(z,filename,*a,**kw):
        if str(filename).endswith("218857879d6287b87460540cea2d8ec053df7685.png"): return
        return saved(z,filename,*a,**kw)
    zipfile.ZipFile.write=skip
runpy.run_path(sys.argv[2],run_name="__main__")
''')

results = []


def case(name, mutate=None, fault=None, expected_error=None):
    folder = SCRATCH / name
    folder.mkdir()
    template = folder / "template"
    shutil.copytree(baseline, template)
    if mutate:
        mutate(template)
    output = folder / "article.docx"
    output.write_bytes(article_bytes)
    env = dict(os.environ, ARTICLE_TEMPLATE=str(template),
               ARTICLE_MD=str(ROOT / "article/article.md"), ARTICLE_DOCX=str(output))
    env.pop("ARTICLE_REFS", None)
    args = [sys.executable, "-I"]
    if fault:
        args += [str(wrapper), fault, str(BUILDER)]
    else:
        args += [str(BUILDER)]
    cp = subprocess.run(args, cwd=folder, env=env, capture_output=True, text=True)
    final_bytes = output.read_bytes()
    record = {"name": name, "command": args, "cwd": str(folder),
              "returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr,
              "destination_preserved": final_bytes == article_bytes,
              "before_sha256": sha(article_bytes), "after_sha256": sha(final_bytes),
              "temporary_archive_exists": Path(str(output) + ".tmp-build").exists()}
    if expected_error:
        record["expected_diagnostic"] = expected_error
        record["passed"] = (cp.returncode != 0 and record["destination_preserved"]
                            and not record["temporary_archive_exists"]
                            and expected_error in (cp.stdout + cp.stderr))
    else:
        with zipfile.ZipFile(output) as z:
            record["zip_crc_error"] = z.testzip()
            record["exact_current_document_xml_match"] = z.read("word/document.xml") == article_xml
            names = set(z.namelist())
            record["removed_part_relationships_absent"] = not any(
                "word/_rels/" + part + ".rels" in names
                for part in ("footnotes.xml", "endnotes.xml", "numbering.xml", "footer1.xml"))
        record["passed"] = (cp.returncode == 0 and record["zip_crc_error"] is None
                            and record["exact_current_document_xml_match"]
                            and record["removed_part_relationships_absent"]
                            and not record["temporary_archive_exists"])
    results.append(record)


def delete(part):
    return lambda template: (template / part).unlink()


case("normal_from_unrelated_directory")
for n, figure in enumerate(FIGURES, 1):
    part = "word/media/" + figure
    case("missing_figure_" + str(n), delete(part), expected_error=part)
for part in ("word/styles.xml", "word/settings.xml", "word/theme/theme1.xml", "word/fontTable.xml",
             "[Content_Types].xml", "_rels/.rels"):
    case("missing_" + part.replace("/", "_").replace("[", "").replace("]", ""),
         delete(part), expected_error=part)
case("empty_figure", lambda t: (t / ("word/media/" + FIGURES[1])).write_bytes(b""),
     expected_error="missing or empty ARTICLE_TEMPLATE part")
case("malformed_styles", lambda t: (t / "word/styles.xml").write_text("<broken>"),
     expected_error="invalid ARTICLE_TEMPLATE XML: word/styles.xml")
case("missing_root_metadata_dependency", delete("docProps/core.xml"),
     expected_error="absent part: /docProps/core.xml")


def wrong_style_type(template):
    path = template / "[Content_Types].xml"
    tree = ET.parse(path)
    for node in tree.getroot():
        if node.get("PartName") == "/word/styles.xml":
            node.set("ContentType", "application/xml")
    tree.write(path, encoding="utf-8", xml_declaration=True)


case("incorrect_style_content_type", wrong_style_type,
     expected_error="incorrect content type for word/styles.xml")


def missing_font_dependency(template):
    path = template / "word/_rels/fontTable.xml.rels"
    tree = ET.parse(path)
    ET.SubElement(tree.getroot(), "{" + REL_NS + "}Relationship", {
        "Id": "rIdExtra", "Type": DOC_REL_NS + "/font", "Target": "fonts/missing.odttf"})
    tree.write(path, encoding="utf-8", xml_declaration=True)


case("missing_transitive_font_dependency", missing_font_dependency,
     expected_error="missing relationship target: word/_rels/fontTable.xml.rels rIdExtra")


def orphan_relationship(template):
    (template / "word/_rels/absent.xml.rels").write_text(
        '<Relationships xmlns="' + REL_NS + '"/>')


case("orphan_retained_relationship", orphan_relationship,
     expected_error="orphan relationship part")


def unresolved_id(template):
    path = template / "word/fontTable.xml"
    tree = ET.parse(path)
    tree.getroot().set("{" + DOC_REL_NS + "}id", "rIdMissing")
    tree.write(path, encoding="utf-8", xml_declaration=True)


case("unresolved_relationship_id", unresolved_id,
     expected_error="unresolved relationship ID in word/fontTable.xml: rIdMissing")


def incorrect_root_document(template):
    path = template / "_rels/.rels"
    tree = ET.parse(path)
    for node in tree.getroot():
        if node.get("Type") == DOC_REL_NS + "/officeDocument":
            node.set("Target", "docProps/core.xml")
    tree.write(path, encoding="utf-8", xml_declaration=True)


case("incorrect_root_document", incorrect_root_document,
     expected_error="package root does not reference word/document.xml")


def duplicate_root_document(template):
    path = template / "_rels/.rels"
    tree = ET.parse(path)
    ET.SubElement(tree.getroot(), "{" + REL_NS + "}Relationship", {
        "Id": "rIdSecondDocument", "Type": DOC_REL_NS + "/officeDocument", "Target": "word/document.xml"})
    tree.write(path, encoding="utf-8", xml_declaration=True)


case("duplicate_root_office_document", duplicate_root_document,
     expected_error="exactly one office document")


def external_font_relationship(template):
    path = template / "word/_rels/fontTable.xml.rels"
    tree = ET.parse(path)
    ET.SubElement(tree.getroot(), "{" + REL_NS + "}Relationship", {
        "Id": "rIdExternal", "Type": DOC_REL_NS + "/font",
        "Target": "https://example.invalid/font", "TargetMode": "External"})
    tree.write(path, encoding="utf-8", xml_declaration=True)


case("external_relationship_not_local_part", external_font_relationship)
for phase, diagnostic in (("archive_write", "synthetic fifth archive write failure"),
                          ("integrity_check", "archive failed its own integrity check"),
                          ("fsync", "synthetic fsync failure"),
                          ("replace", "synthetic atomic replacement failure"),
                          ("semantic_missing_image", "article package is missing required parts")):
    case("failure_" + phase, fault=phase, expected_error=diagnostic)


def fixture_identities(folder):
    identities = {}
    for item in sorted(folder.rglob("*")):
        relative = str(item.relative_to(folder))
        if item.is_symlink():
            identities[relative] = {"symlink": os.readlink(item)}
        elif item.is_file():
            identities[relative] = {"sha256": sha(item.read_bytes())}
        else:
            identities[relative] = {"directory": True}
    return identities


def collision_case(name, arrange):
    folder = SCRATCH / name
    folder.mkdir()
    template = folder / "template"
    shutil.copytree(baseline, template)
    output = folder / "article.docx"
    output.write_bytes(article_bytes)
    cwd, source, destination, md = arrange(folder, template, output)
    original = fixture_identities(folder)
    env = dict(os.environ, ARTICLE_TEMPLATE=str(source),
               ARTICLE_MD=str(md or ROOT / "article/article.md"), ARTICLE_DOCX=str(destination))
    env.pop("ARTICLE_REFS", None)
    args = [sys.executable, "-I", str(BUILDER)]
    cp = subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True)
    current = fixture_identities(folder)
    preserved = original == current
    results.append({"name": name, "command": args, "cwd": str(cwd),
                    "returncode": cp.returncode, "stdout": cp.stdout, "stderr": cp.stderr,
                    "expected_diagnostic": "unsafe build paths",
                    "destination_preserved": destination.read_bytes() == article_bytes
                        if destination.is_file() else None,
                    "template_and_all_fixture_bytes_preserved": preserved,
                    "fixture_identities_before": original,
                    "fixture_identities_after": current,
                    "passed": cp.returncode != 0 and preserved
                              and "unsafe build paths" in (cp.stdout + cp.stderr)})


def source_equals_work(folder, template, output):
    work = folder / "article_pkg"
    template.rename(work)
    return folder, work, output, None


def source_inside_work(folder, template, output):
    work = folder / "article_pkg"
    work.mkdir()
    source = work / "nested_template"
    template.rename(source)
    return folder, source, output, None


def source_contains_work(folder, template, output):
    (template / "article_pkg").mkdir()
    (template / "article_pkg/sentinel").write_bytes(b"keep ancestor work bytes")
    return template, template, output, None


def source_symlink_to_work(folder, template, output):
    work = folder / "article_pkg"
    template.rename(work)
    source = folder / "source_alias"
    source.symlink_to(work, target_is_directory=True)
    return folder, source, output, None


def work_symlink_to_source(folder, template, output):
    (folder / "article_pkg").symlink_to(template, target_is_directory=True)
    return folder, template, output, None


def destination_inside_work(folder, template, output):
    work = folder / "article_pkg"
    work.mkdir()
    destination = work / "article.docx"
    output.rename(destination)
    return folder, template, destination, None


def destination_lexically_inside_work(folder, template, output):
    work = folder / "article_pkg"
    work.mkdir()
    destination = work / "alias.docx"
    destination.symlink_to(output)
    return folder, template, destination, None


def destination_resolves_inside_work(folder, template, output):
    work = folder / "article_pkg"
    work.mkdir()
    target = work / "article.docx"
    output.rename(target)
    output.symlink_to(target)
    return folder, template, output, None


def temporary_resolves_inside_work(folder, template, output):
    work = folder / "article_pkg"
    work.mkdir()
    target = work / "keep.bin"
    target.write_bytes(b"keep temporary alias bytes")
    Path(str(output) + ".tmp-build").symlink_to(target)
    return folder, template, output, None


def destination_hardlink_in_work(folder, template, output):
    work = folder / "article_pkg"
    work.mkdir()
    os.link(output, work / "old_article.docx")
    return folder, template, output, None


def temporary_hardlink_to_destination(folder, template, output):
    os.link(output, str(output) + ".tmp-build")
    return folder, template, output, None


def destination_inside_template(folder, template, output):
    target = template / "old_article.docx"
    output.rename(target)
    return folder, template, target, None


def temporary_hardlink_to_input(folder, template, output):
    md = folder / "article.md"
    shutil.copyfile(ROOT / "article/article.md", md)
    os.link(md, str(output) + ".tmp-build")
    return folder, template, output, md


for arranger in (source_equals_work, source_inside_work, source_contains_work,
                 source_symlink_to_work, work_symlink_to_source, destination_inside_work,
                 destination_lexically_inside_work, destination_resolves_inside_work,
                 temporary_resolves_inside_work, destination_hardlink_in_work,
                 temporary_hardlink_to_destination, destination_inside_template,
                 temporary_hardlink_to_input):
    collision_case("collision_" + arranger.__name__, arranger)

builder_after = sha(BUILDER.read_bytes())
report = {"scope": "Scratch document packages only; no scientific code executed or deliverable written.",
          "python": sys.executable, "scratch_directory": str(SCRATCH),
          "builder_sha256_before": builder_before, "builder_sha256_after": builder_after,
          "template_docx_sha256_at_start": sha(template_bytes),
          "article_docx_sha256_at_start": sha(article_bytes),
          "test_driver_sha256": sha(Path(__file__).read_bytes()),
          "results": results,
          "all_passed": all(r["passed"] for r in results) and builder_before == builder_after}
EVIDENCE.write_text(json.dumps(report, indent=2) + "\n")
print(json.dumps({"evidence": str(EVIDENCE), "scratch": str(SCRATCH),
                  "all_passed": report["all_passed"], "tests": len(results),
                  "failures": [r["name"] for r in results if not r["passed"]]}, indent=2))
if not report["all_passed"]:
    sys.exit(1)
