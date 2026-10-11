#!/usr/bin/env python3
"""Review document helpers with harmless synthetic OOXML, outside the sources."""
import ast
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(__file__).resolve().parent
SCRIPT = ROOT / "tools/apply_edits.py"
XML = '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>alpha</w:t></w:r></w:p></w:body></w:document>'


def identity(p):
    b = p.read_bytes()
    return {"path": str(p), "bytes": len(b), "sha256": hashlib.sha256(b).hexdigest()}


def run_case(name, xml, edits):
    with tempfile.TemporaryDirectory(prefix="pf8_synthetic_edit_") as d:
        p = Path(d)
        (p / "word").mkdir()
        source = p / "word/document.xml"
        source.write_text(xml)
        edit_file = p / "edits.json"
        edit_file.write_text(json.dumps(edits))
        environment = {**os.environ, "EDITS": str(edit_file), "DRY": "0", "LEFTOVER": str(p / "leftover.json")}
        r = subprocess.run([sys.executable, "-I", str(SCRIPT)], cwd=p, env=environment, capture_output=True, text=True)
        result = source.read_text()
        return {"case": name, "input_xml": xml, "edits": edits, "exit_code": r.returncode,
                "stdout": r.stdout, "stderr": r.stderr, "output_xml": result,
                "source_changed": result != xml, "leftover": json.loads((p / "leftover.json").read_text()) if (p / "leftover.json").exists() else None}


def main():
    tool_files = [ROOT / "tools" / n for n in ("apply_edits.py", "build_article.py", "make_supplement.py")]
    syntax = {}
    for p in tool_files:
        ast.parse(p.read_text(), filename=str(p))
        syntax[p.name] = True
    tree = ast.parse((ROOT / "tools/build_article.py").read_text())
    refs = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "REFS" for t in n.targets))
    full = lambda quote, repl: {"quote": quote, "repl": repl, "concept": "synthetic review", "sev": "P2"}
    cases = [run_case("documented_two_key_schema", XML, [{"quote": "alpha", "repl": "BETA"}]),
             run_case("one_valid_one_missing", XML, [full("alpha", "BETA"), full("not present", "GAMMA")]),
             run_case("duplicate_quote", XML.replace('>alpha<', '>alpha alpha<'), [full("alpha", "BETA")])]
    assertions = {
        "documented_schema_raises_key_error": cases[0]["exit_code"] != 0 and "KeyError" in cases[0]["stderr"],
        "missing_edit_does_not_prevent_partial_write": cases[1]["exit_code"] == 0 and cases[1]["source_changed"] and len(cases[1]["leftover"]) == 1,
        "duplicate_quote_silently_changes_only_first_occurrence": cases[2]["exit_code"] == 0 and "BETA alpha" in cases[2]["output_xml"],
        "article_references_depend_on_absolute_external_path": Path(refs).is_absolute() and not str(Path(refs)).startswith(str(ROOT) + "/"),
    }
    evidence = {"generated_utc": datetime.now(timezone.utc).isoformat(), "runtime": sys.executable,
                "checker": identity(Path(__file__).resolve()), "sources": [identity(p) for p in tool_files] + [identity(ROOT / "tools/README.md")],
                "syntax_parse": syntax, "references_dependency": {"path": refs, "exists_on_review_machine": Path(refs).exists(), "inside_repository": False},
                "synthetic_cases": cases, "confirmed_findings": assertions,
                "scope": "Only document helpers were run, on synthetic OOXML in disposable temporary directories. No manuscript or scientific source was edited; the article/supplement builders were not run."}
    (OUT / "build_tools_validation.json").write_text(json.dumps(evidence, indent=2) + "\n")
    print(json.dumps({"confirmed": sum(assertions.values()), "total": len(assertions), "references_file_exists": Path(refs).exists()}))
    return 0 if all(assertions.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
