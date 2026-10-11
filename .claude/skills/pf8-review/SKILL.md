---
name: pf8-review
description: Run an adversarial review of a Pf8 Ghana document - sweeping by defect concept across the whole document, then refuting each finding before it is acted on. Use before calling any draft finished, and to triage an incoming external review.
---

# Adversarial review

Two modes. Both end with findings that survived an attempt to refute them.

---

## Mode A — review our own document

**Never sweep by phrase.** Every round of this project has fixed the named wording of a claim and
left the same claim standing elsewhere. One concept-major sweep found **93** instances of nine
defects an external reviewer had spotted about 12 of.

1. **Dump the document by section** so agents can grep it:

```bash
cd /private/tmp/.../scratchpad && mkdir -p msdump
# unzip the .docx, then flatten <w:p> elements to text, one file per top-level heading
```

2. **One agent per defect concept**, not per section — each sweeping all sections for every
   phrasing of its idea, checking table cells, figure captions, status columns and one-line answer
   rows specifically. Give each the forbidden-claims list from `CLAUDE.md` and
   `article/CANONICAL_FACTS_FOR_ARTICLE.md` as ground truth.

3. **Adversarial pass.** For each proposed edit, a fresh agent that defaults to rejecting it and
   must check: does the quote appear *verbatim*; is the statement actually wrong against the facts;
   is it a correction record deliberately quoting a withdrawn claim; would the replacement introduce
   a new error? Roughly a third get rejected — that is the pass working.

4. **Apply with assertions.** Every substitution asserts its occurrence count and the file is
   written only at the end, so an abort leaves it untouched.

5. **Re-read every correction record** that mentions what you just fixed. Fixing the body can make a
   note false, and a note claiming a fix that was not made is worse than the original defect.

Use the `pf8-reviewer` subagent for the sweep and the refutation. Give it the artefact, not your
conclusion.

---

## Mode B — triage an incoming external review

The reviewer on this project has been right on every substantive finding across four rounds, and
twice a correct finding was wrongly dismissed here. So:

1. **Verify each claim empirically before agreeing or disagreeing.** Recompute; md5 the inputs;
   establish cohorts from construction. Most claims are settled in one command.
2. **Expect to be wrong.** When a finding contradicts something you asserted confidently, that is
   the one to check hardest.
3. **Check the census, not just the instance.** A reviewer naming three cases usually means more.
4. **Say plainly which findings are wrong, with the evidence** — and fix the underlying cause. When
   a reviewer was misled by a stale local file, the fix is to archive the right file under an
   unambiguous name, not merely to win the point.
5. Commit each correction separately with the reasoning in the message.

---

## Report

Group as: **confirmed and fixed** · **confirmed, scope/evidence gap** · **refuted, with evidence** ·
**could not check**. State what the review does not certify.
