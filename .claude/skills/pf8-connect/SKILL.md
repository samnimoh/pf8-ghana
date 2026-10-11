---
name: pf8-connect
description: Connect to the Pf8 analysis server (gyadu/bacg2), verify the environment, and run a read-only query or job against the pipeline or the Pf8 Zarr store. Use whenever work needs server data.
---

# Working on the analysis server

```bash
ssh gyadu        # 192.168.0.152 · user gyadu · key ~/.ssh/id_ed25519_gyadu · hostname bacg2
```

Key-based login works. **Never enter, request or generate a password.**

## Environment

There is no `conda` on the non-login `PATH`, so `conda activate` fails. Call the interpreter directly:

```bash
ssh gyadu '/home/gyadu/.conda/envs/spatial/bin/python -c "import numpy, pandas, zarr, numcodecs, requests; print(\"ok\")"'
```

| | |
|---|---|
| Project root | `/media/biodataA/pf8/gyadu/` (`scripts data interim results figures logs`) |
| Python | `/home/gyadu/.conda/envs/spatial/bin/python` (3.10) |
| Pf8 Zarr | `https://pf8-release.cog.sanger.ac.uk/zarr` — public, reachable from the server |
| Disk | ~94% full. **Do not write large intermediates.** |

## Rules

- **Read-only by default.** Never modify anything under the project root that is not part of this
  pipeline. Put scratch scripts in the server's `/tmp` and pass paths as arguments.
- Copy a script up with `scp`, run it, copy the log back. Do not edit pipeline scripts in place.
- Long jobs: `nohup <cmd> > /tmp/x.log 2>&1 &`, then poll `/tmp/x.log`. Do **not** write shell
  `until` loops waiting on a workflow journal — they burn their timeout.

## Querying the Pf8 Zarr

Working patterns are already archived — reuse them rather than rewriting:
`provenance_final/audit_scripts/` (`check_n458d.py`, `check_domain.py`, `check_coverage.py`, …).
They fetch variant metadata and genotypes over HTTPS with a threaded session.

Two gotchas those scripts encode:
- `samples` and other object-dtype arrays have **no compressor** — decode via `filters[0]`, not
  `compressor`, or you get `TypeError: 'NoneType' object is not iterable`.
- Genotype fetches are large. Restrict to the variant chunk and the sample chunks you need; a
  careless fetch pulls gigabytes.

## Before you trust an output

md5 it against the local copy, and establish its cohort from the **submatrix shape or row count
printed by the generating log**, never from the filename. See `corrected/DIMRED_FILENAME_WARNING.md`
for the case where the names are inverted and both logs lie about where they wrote.
