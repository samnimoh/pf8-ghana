"""Exercise the actual majority-resolution source without importing its pipeline.

The unmodified function body is AST-extracted. Only callset retrieval and the
genotype/metadata wrappers are replaced by in-memory fixtures. These finite
checks connect the Lean reference rule to this Python function for the covered
inputs; they are not a proof of the whole Python implementation or its I/O.
"""
from __future__ import annotations

import ast
import contextlib
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "v2/scripts/step04a_prepare_callset.py"
OUTPUT = Path(__file__).with_name("majority_validation.json")


def run_check() -> dict:
    source_text = SOURCE.read_text()
    tree = ast.parse(source_text)
    fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef)
              and n.name == "resolve_mixed_calls")
    # Avoid evaluating third-party type annotations, retaining the full body.
    for arg in fn.args.args:
        arg.annotation = None
    fn.returns = None
    module = ast.fix_missing_locations(ast.Module(body=[fn], type_ignores=[]))

    cases = []
    expected = []
    depths = []
    for encoding in ((0, 1), (1, 0), (0, 0), (1, 1), (-1, -1)):
        for ref in range(-1, 17):
            for alt in range(-1, 17):
                cases.append(encoding)
                depths.append((ref, alt))
                if encoding in ((0, 1), (1, 0)):
                    r, a = max(ref, 0), max(alt, 0)
                    allele = 0 if r > a else 1 if a > r else -1
                    expected.append((allele, allele))
                else:
                    expected.append(encoding)
    ad = np.array(depths, dtype=np.int16)[:, None, :]
    gt = SimpleNamespace(values=np.array(cases, dtype=np.int8)[:, None, :])
    selection = SimpleNamespace(iloc=SimpleNamespace())

    class Indexer:
        def __getitem__(self, rows):
            return rows

    selection.iloc = Indexer()
    retrieval = SimpleNamespace(
        has_field=lambda root, field: True,
        take_calldata=lambda root, rows, field, n_alleles: ad[rows],
    )
    scope = {"np": np, "cio": retrieval}
    exec(compile(module, str(SOURCE), "exec"), scope)
    logs = io.StringIO()
    with contextlib.redirect_stdout(logs):
        scope["resolve_mixed_calls"](
            gt, None, selection, np.array([0]), block=19)
    expected_array = np.array(expected, dtype=np.int8)[:, None, :]
    mismatches = np.flatnonzero(np.any(gt.values != expected_array, axis=(1, 2)))
    check = {
        "check": "actual majority function agrees with declarative reference rule",
        "passed": len(mismatches) == 0,
        "cases": len(cases),
        "depth_range_inclusive": [-1, 16],
        "encodings": [list(x) for x in ((0, 1), (1, 0), (0, 0), (1, 1), (-1, -1))],
        "block_size": 19,
        "mismatch_indices": mismatches.tolist(),
    }
    return {
        "source": str(SOURCE),
        "source_sha256": hashlib.sha256(SOURCE.read_bytes()).hexdigest(),
        "numpy_version": np.__version__,
        "checks": [check],
        "all_checks_passed": check["passed"],
        "limitations": [
            "Only the majority resolver function is exercised, with mocked AD retrieval.",
            "This does not verify sample/variant I/O alignment, third-party libraries, or the complete pipeline.",
            "Finite agreement does not establish formal refinement of arbitrary Python executions.",
            "The available v2 script is an earlier snapshot, not the missing final executed script.",
        ],
    }


if __name__ == "__main__":
    result = run_check()
    OUTPUT.write_text(json.dumps(result, indent=2) + "\n")
    print(f"Majority resolver: {result['checks'][0]['cases']} cases, "
          f"passed={result['all_checks_passed']}")
    raise SystemExit(0 if result["all_checks_passed"] else 1)
