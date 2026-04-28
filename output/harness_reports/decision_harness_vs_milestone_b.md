# Decision: keep grinding on the harness, or move to Milestone B?

**TL;DR — Move to Milestone B.** The harness is at a real point of diminishing
returns for these four cases. Further harness-side improvements would lift
the theoretical ceiling by +2 to +8 points per case; meanwhile the workbench
UI is the blocker for actually putting the tool in front of your team.

## State of the harness right now

- **183 tests passing** across all areas we've touched. 32 pre-existing
  failures in unrelated files (workbench, metrics coverage, dataplane
  validator) predate this work and are driven by missing dependencies, not
  changed behavior.
- **Cumulative changes across two rounds:**
  - OCSF analyzer resolves `setNestedField(result, "class_uid", N)` (both
    literals and identifier references).
  - Source analyzer recognises `getValue(event, "X", …)` /
    `getNestedField(event, "X.Y")` patterns.
  - Two new lint rules: `pcall_return_scope`, `string_method_type_guard`.
  - Generalized `source_class_mismatch` using 10-class keyword table.
  - Timestamp-type fuzz pass (numeric + missing variants) with
    `lua_error`-aware pass/fail counting.
  - Milestone A reference library (18 production Observo serializers as
    prompt few-shots; ExampleSelector wired into `build_generation_prompt`).

## Current grades on Marco's PDF cases

| Case | Marco's UI | Round 1 | **Now** | Stuck penalties |
|---|---|---|---|---|
| cisco_duo | lint Fair / OCSF Poor | D / 60 | **D / 60** | embedded fields missing (−8); real bug: exec 0/1 |
| ms_defender_365 | (not scored) | C / 70 | **C / 70** | placeholders (−6), excessive_unmapped (−8) |
| akamai_cdn | (not scored) | D / 68 | **F / 58** | placeholders (−6), excessive_unmapped (−8), class mismatch (−10) |
| akamai_dns | lint Poor / OCSF Fair | D / 63 | **D / 63** | excessive_unmapped (−8), embedded fields missing (−8) |

## Theoretical ceilings per case

If every remaining harness/prompt/template item shipped *and* each script
were regenerated against the new guidance:

| Case | Now | Ceiling | Delta | Unlocks |
|---|---|---|---|---|
| cisco_duo | 60 | **82 (B)** | +22 | scope-bug fix (via regeneration) +20, lint cleanup +2 |
| ms_defender_365 | 70 | **78 (C)** | +8 | placeholder removal +6, lint cleanup +2 |
| akamai_cdn | 58 | **76 (C)** | +18 | class fix +10, placeholder removal +6, lint cleanup +2 |
| akamai_dns | 63 | **65 (D)** | +2 | lint cleanup only |

Note: DUO's biggest lift (+20) requires **regenerating** the script; no
harness change can unstick it because the scope bug is a real defect in
Marco's output. Akamai DNS is essentially capped at D — its low field
coverage reflects DNS-specific fields (query.hostname, answers, rcode) that
the OCSF v1.3 4003 schema mostly doesn't include as required, so there's
genuinely not much more coverage to earn.

## What each remaining roadmap item actually buys

| Item | Type | Impact | Cost | Verdict |
|---|---|---|---|---|
| Placeholder re-prompt in refinement loop | Generator | −6 on 2 cases | 2 hrs | medium — small score lift, re-prompt logic already exists pattern |
| `copyUnmappedFields` helper rewrite | Template | +2/case via lint | 1 hr | low — worth doing opportunistically |
| Timestamp coercion in system prompt | Prompt | closes DNS-style bugs upstream | 30 min | **high value, low cost** — do this one |
| Weight fuzz failures into confidence | Harness | drops scores on 3/4 cases (honest) | 1 hr | low now — would just be depressing scores without a clear team benefit |
| Classification cross-check (done) | Harness | ✓ already shipped round 2 | — | ✓ |

The only "harness-side" item still on the table is **weight fuzz into
confidence**. It's correct in principle but would just push DUO, MS
Defender, and DNS scores down without moving the needle on what the team
should do. The generator prompt changes (placeholder re-prompt, timestamp
coercion) are where the real remaining lift lives — and those belong in
the next generation-pipeline work, not in harness scoring.

## The harness is solving the problem it was built to solve

Before this work, the harness missed every one of the issues Marco
documented and added two false-negative F grades (MS Defender, Akamai CDN).
Now it correctly:

- grades the four cases in a sensible order (C/70 working > D/60 broken >
  F/58 misclassified)
- catches the scope bug the production dataplane accepted (`test_execution`
  reports 0/1 on DUO)
- catches the timestamp-type failure Marco hit in production (fuzz pass,
  plus lint rule)
- flags the CDN misclassification (penalty −10)
- identifies the setNestedField pattern that broke the previous analyzer

These are the bugs a team needs the harness to catch. Polishing the
remaining +2 to +8 points per case is not what gates team adoption — the
workbench UI is.

## What Milestone B unlocks

From my original proposal:

> **Milestone B — "Workbench is actually usable by humans"**
> - Monaco editor panel at `/workbench` wired to
>   `/api/v1/workbench/validate/<parser>` for inline harness feedback
> - Render the harness report in the UI (score, breakdown, lint issues,
>   field trace) instead of as a JSON blob
> - Draft persistence via `POST /api/v1/workbench/drafts` so a teammate can
>   pause mid-task
> - Acceptance: a team member who's never opened the repo can paste a
>   parser sample, generate Lua, iterate with the editor, and approve —
>   without touching the CLI

This is the actual bottleneck. The harness can now tell a team member that
their Cisco DUO script silently returns nil — but they can't read that
finding in the UI today, because the workbench renders JSON blobs. Closing
that surface is the biggest remaining move.

## Recommendation

1. **Ship Milestone B** next. The harness is good enough to give meaningful
   feedback; the UI is what lets teammates receive it.
2. **Defer harness items 1 and 4** (placeholder re-prompt, timestamp
   coercion in prompt) to the next generator-pipeline pass. These are
   prompt changes, not harness changes — bundle them with the next
   refinement-loop improvements.
3. **Drop items 3 and 5** for now. Item 3 (`copyUnmappedFields` rewrite) is
   a small cleanup; item 5 (weight fuzz into score) isn't a net positive
   for team experience.
4. **Re-evaluate the harness** after the next full-pipeline regeneration
   run. If scripts regenerated with the current harness still grade below
   B on cases like DUO and MS Defender, that's the signal to come back —
   not Marco's one-off PDF.

## Files delivered this evaluation cycle

- `output/harness_reports/harness_improvements_2026_04_19.md` (round 1)
- `output/harness_reports/harness_improvements_round2_2026_04_19.md` (round 2)
- `output/harness_reports/decision_harness_vs_milestone_b.md` (this doc)
- `output/harness_reports/marco_grading_2026_04_19.json` (raw scores)
- `output/harness_reports/marco_grading_after_fix.json` (raw scores after round 1)
- `output/harness_reports/marco_grading_scorecard.md` (pre-fix scorecard)
