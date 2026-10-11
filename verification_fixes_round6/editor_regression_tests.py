"""Exercise the edit helper only on synthetic or copied XML in temporary folders.

Run with the bundled Python using -I. No source DOCX or scientific output is changed.
"""

import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import xml.etree.ElementTree as ET
import zipfile
from xml.sax.saxutils import escape


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "tools/apply_edits.py"
RESULT = Path(__file__).with_name("editor_regression_results.json")
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
RESULTS = []


def paragraph(*runs):
    return "<w:p>" + "".join(
        '<w:r><w:t xml:space="preserve">' + escape(text) + "</w:t></w:r>"
        for text in runs
    ) + "</w:p>"


def document(*blocks):
    return ('<?xml version="1.0" encoding="UTF-8"?><w:document '
            'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body>" + "".join(blocks) + "</w:body></w:document>")


def texts(xml):
    return ["".join(t.text or "" for t in p.iter(W + "t"))
            for p in ET.fromstring(xml).iter(W + "p")]


def run_case(name, xml, edits, expected_code, expected_texts=None,
             unchanged=False, expected_leftover=None, env_overrides=None,
             expected_stdout=None, retain_texts=True):
    with tempfile.TemporaryDirectory(prefix="pf8_editor_fix_") as temporary:
        folder = Path(temporary)
        (folder / "word").mkdir()
        path = folder / "word/document.xml"
        path.write_text(xml, encoding="utf-8")
        original = path.read_bytes()
        edits_path, leftover_path = folder / "edits.json", folder / "leftover.json"
        edits_path.write_text(json.dumps(edits), encoding="utf-8")
        env = dict(os.environ, EDITS=str(edits_path), DRY="0", LEFTOVER=str(leftover_path))
        env.pop("ALLOW_PARTIAL", None)
        env.update(env_overrides or {})
        result = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=folder,
                                env=env, text=True, capture_output=True)
        after = path.read_bytes()
        observed_texts = texts(after)
        leftover = json.loads(leftover_path.read_text()) if leftover_path.exists() else None
        assert result.returncode == expected_code, (name, result.stdout, result.stderr)
        if expected_texts is not None:
            assert observed_texts == expected_texts, (name, observed_texts)
        if unchanged:
            assert original == after, (name, "XML changed despite rejection")
        if expected_leftover is not None:
            assert leftover == expected_leftover, (name, leftover)
        if expected_stdout:
            assert expected_stdout in result.stdout, (name, result.stdout)
        RESULTS.append({
            "name": name, "status": "passed", "returncode": result.returncode,
            "xml_unchanged": original == after,
            "paragraph_texts": observed_texts if retain_texts else None,
            "paragraph_count": len(observed_texts),
            "xml_sha256_before": hashlib.sha256(original).hexdigest(),
            "xml_sha256_after": hashlib.sha256(after).hexdigest(),
            "leftover": leftover, "stdout": result.stdout, "stderr": result.stderr,
        })
        return after, leftover


edit = {"quote": "alpha beta", "repl": "new phrase"}
run_case("optional_metadata_unique", document(paragraph("alpha beta")), [edit], 0,
         ["new phrase"], expected_leftover=[])
run_case("exact_duplicates_rejected", document(paragraph("alpha beta"), paragraph("alpha beta")),
         [edit], 1, unchanged=True, expected_leftover=[edit], expected_stdout="2 matches")
run_case("whitespace_duplicates_rejected", document(paragraph("alpha  beta"), paragraph("alpha   beta")),
         [edit], 1, unchanged=True, expected_leftover=[edit], expected_stdout="2 matches")
run_case("mixed_exact_and_variant_rejected", document(paragraph("alpha beta"), paragraph("alpha  beta")),
         [edit], 1, unchanged=True, expected_leftover=[edit], expected_stdout="2 matches")
selected = dict(edit, occurrence=2)
run_case("spacing_occurrence_second", document(paragraph("alpha  beta"), paragraph("alpha   beta")),
         [selected], 0, ["alpha  beta", "new phrase"], expected_leftover=[])
run_case("mixed_exact_occurrence_document_order", document(paragraph("alpha  beta"), paragraph("alpha beta")),
         [selected], 0, ["alpha  beta", "new phrase"], expected_leftover=[])
run_case("single_occurrence_one", document(paragraph("alpha beta")), [dict(edit, occurrence=1)], 0,
         ["new phrase"], expected_leftover=[])
for number, invalid in enumerate((0, -1, 2, True, False, "1", 1.0, None)):
    bad_edit = dict(edit, occurrence=invalid)
    run_case(f"invalid_occurrence_{number}_{type(invalid).__name__}", document(paragraph("alpha beta")),
             [bad_edit], 1, unchanged=True, expected_leftover=[bad_edit])
outside = dict(edit, occurrence=3)
run_case("duplicate_occurrence_out_of_range", document(paragraph("alpha beta"), paragraph("alpha beta")),
         [outside], 1, unchanged=True, expected_leftover=[outside])
overlapping = {"quote": "aaa", "repl": "new"}
run_case("overlapping_locations_rejected", document(paragraph("aaaa")), [overlapping], 1,
         unchanged=True, expected_leftover=[overlapping], expected_stdout="2 matches")
run_case("quote_spanning_formatting_runs", document(paragraph("before alpha ", "beta after")), [edit], 0,
         ["before new phrase after"], expected_leftover=[])
run_case("all_quote_whitespace_normalized", document(paragraph("alpha\t\nbeta")),
         [{"quote": "alpha\n beta", "repl": "new phrase"}], 0, ["new phrase"], expected_leftover=[])
crossing = {"quote": "onestart", "repl": "merged"}
run_case("paragraph_boundary_not_joined", document(paragraph("end of one"), paragraph("start of next")),
         [crossing], 1, unchanged=True, expected_leftover=[crossing])
cells = "<w:tbl><w:tr><w:tc>" + paragraph("end of one") + "</w:tc><w:tc>" + paragraph("start of next") + "</w:tc></w:tr></w:tbl>"
run_case("table_cell_boundary_not_joined", document(cells), [crossing], 1,
         unchanged=True, expected_leftover=[crossing])
nested = "<w:p><w:r><w:t>end of one</w:t></w:r><w:p/><w:r><w:t>start of next</w:t></w:r></w:p>"
run_case("empty_nested_paragraph_boundary_not_joined", document(nested), [crossing], 1,
         unchanged=True, expected_leftover=[crossing])
for tag in ("tab", "br", "cr"):
    control = f"<w:p><w:r><w:t>end of one</w:t><w:{tag}/><w:t>start of next</w:t></w:r></w:p>"
    run_case(f"explicit_{tag}_not_silently_removed", document(control), [crossing], 1,
             unchanged=True, expected_leftover=[crossing])
displayed_controls = {
    "sym": ' w:font="Wingdings" w:char="F0A3"',
    "noBreakHyphen": "", "softHyphen": "", "pgNum": "",
    "footnoteReference": ' w:id="1"', "endnoteReference": ' w:id="1"',
    "commentReference": ' w:id="1"', "annotationRef": "",
    "footnoteRef": "", "endnoteRef": "", "separator": "", "continuationSeparator": "",
    "ptab": ' w:alignment="left" w:relativeTo="margin" w:leader="none"',
}
for tag, attributes in displayed_controls.items():
    marker = f"<w:{tag}{attributes}/>"
    control = "<w:p><w:r><w:t>end of one</w:t>" + marker + "<w:t>start of next</w:t></w:r></w:p>"
    run_case(f"displayed_{tag}_boundary_not_joined", document(control), [crossing], 1,
             unchanged=True, expected_leftover=[crossing])
within_control = ('<w:p><w:r><w:t>alpha beta</w:t><w:footnoteReference w:id="1"/>'
                  '<w:t> tail</w:t></w:r></w:p>')
after, _ = run_case("edit_within_reference_boundary_preserves_marker", document(within_control), [edit], 0,
                    ["new phrase tail"], expected_leftover=[])
assert b'<w:footnoteReference w:id="1"/>' in after
empty_node = "<w:p><w:r><w:t/><w:t></w:t><w:t xml:space=\"preserve\">alpha </w:t><w:t>beta</w:t></w:r></w:p>"
run_case("empty_text_nodes_and_run_spanning", document(empty_node), [edit], 0,
         ["new phrase"], expected_leftover=[])
run_case("escaped_text_spanning_runs", document(paragraph("A & ", "B < C")),
         [{"quote": "A & B < C", "repl": "D & E > F"}], 0, ["D & E > F"], expected_leftover=[])
missing = {"quote": "not present", "repl": "replacement"}
run_case("unmatched_edit_preserves_all_bytes", document(paragraph("alpha beta")), [edit, missing], 1,
         unchanged=True, expected_leftover=[missing])
run_case("explicit_partial_opt_in", document(paragraph("alpha beta")), [edit, missing], 0,
         ["new phrase"], expected_leftover=[missing], env_overrides={"ALLOW_PARTIAL": "1"})
run_case("dry_run_never_writes", document(paragraph("alpha beta")), [edit], 0,
         unchanged=True, expected_leftover=[], env_overrides={"DRY": "1"})
second = {"quote": "beta", "repl": "B"}
after, deferred = run_case("same_run_conflict_is_deferred", document(paragraph("alpha beta")),
                           [{"quote": "alpha", "repl": "A"}, second], 0, ["A beta"],
                           expected_leftover=[second], expected_stdout="run-conflicts 1")
run_case("documented_conflict_replay_finishes", after.decode("utf-8"), deferred, 0,
         ["A B"], expected_leftover=[])

# Exercise parsing against all current deliverables without editing those files.
copied_sources = []
for relative in ("Pf8_Ghana_manuscript_REVISED.docx", "article/Additional_file_1.docx", "article/Pf8_Ghana_article.docx"):
    source = ROOT / relative
    with zipfile.ZipFile(source) as archive:
        copied_xml = archive.read("word/document.xml")
    run_case("copied_document_parse_" + source.stem, copied_xml.decode("utf-8"), [], 0,
             unchanged=True, expected_leftover=[], env_overrides={"DRY": "1"}, retain_texts=False)
    copied_sources.append({"path": str(source), "sha256": hashlib.sha256(source.read_bytes()).hexdigest()})

output = {"script": str(SCRIPT), "script_sha256": hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
          "driver": str(Path(__file__).resolve()), "driver_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
          "python": sys.executable, "scope": "Synthetic and copied word/document.xml only; no DOCX was modified.",
          "copied_sources": copied_sources, "passed": len(RESULTS), "tests": RESULTS}
RESULT.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
print(f"Passed {len(RESULTS)} editor regression checks; results: {RESULT}")
