# AGENTS.md — Pf8 Ghana

Agent-facing guide. The full project rules are in **[CLAUDE.md](CLAUDE.md)** — read it first;
everything there applies to you. This file covers what is specific to running as an agent here.

## Orientation in one minute

```bash
ssh gyadu 'hostname; ls /media/biodataA/pf8/gyadu'   # analysis server, key-based, no password
cat article/CANONICAL_FACTS_FOR_ARTICLE.md           # the only numbers you may use
git log --oneline | head                             # what has already been corrected
```

## The three things that go wrong here

1. **Stale or mislabelled inputs.** Four of this project's errors were a correct analysis read from
   the wrong file. Before comparing any number, md5 the local copy against the server. Never infer a
   cohort or a date from a filename or a log line.
2. **Partial corrections.** Fixing the named wording of a claim and leaving it standing elsewhere has
   happened every round. Sweep by concept, across the whole document, including tables and captions.
3. **Confident wrongness in both directions.** Verify before agreeing with a review *and* before
   dismissing one.

## Available subagents

| Agent | Use it for |
|---|---|
| `pf8-reviewer` | Adversarial review of a document or claim. Refutes by default. The single highest-value tool in this project. |
| `pf8-verifier` | Checking specific numbers and claims against the canonical facts and the saved outputs, including on the server. |

Spawn the reviewer on anything before you call it finished. Give it the artefact, not your
conclusion — a reviewer handed a hypothesis returns it confirmed.

## Available skills

`/pf8-connect` · `/pf8-status` · `/pf8-verify` · `/pf8-review` · `/pf8-rebuild`

See `.claude/skills/`. `/pf8-status` is the right first call when resuming cold.

## Hard constraints

- Never enter, request or generate a password. Key-based SSH already works.
- Never modify files on the server outside this pipeline; prefer read-only queries. Scratch in `/tmp`.
- Disk on the server is ~94% full. Do not write large intermediates.
- Commit to git after every logical correction, with the reasoning in the message.
- Regenerate every PDF when any source changes.
- If a number is not in `CANONICAL_FACTS_FOR_ARTICLE.md`, write `[NUMBER NOT AVAILABLE]`.
