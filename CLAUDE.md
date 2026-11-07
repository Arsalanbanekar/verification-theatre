# Project: Verification Theatre

Research study for the Apart Research **AI x Epistemics Research Sprint** (13–15 Nov 2026),
Track 2: Trust Infrastructure.

Read `PREREGISTRATION.md` before changing anything about the experimental design.
This file tells you how to build. That file tells you what is being measured and why.

---

## The study in one paragraph

Machine-readable provenance (C2PA / Content Credentials) is being mandated — EU AI Act
Article 50, California SB 942 — and as of C2PA v2.4 (April 2026) manifests can be embedded
in HTML, Markdown and structured text, i.e. the formats AI agents read. The C2PA
specification states explicitly that it makes **no value judgment** about whether content is
good, bad or true: it certifies only that assertions are correctly formed, bound to the
asset, and untampered. The interpretive step is delegated to the "Manifest Consumer" — and
the spec's own language was written assuming that consumer is a human.

We test whether LLMs, acting as Manifest Consumers, respond to **what a mark certifies** or
merely to **the fact that a mark is present**.

The attack this implies needs no forgery: sign your own false document, honestly, and the
model upgrades its credence. Everything in the certificate is true. Only the inference is
wrong.

---

## Non-negotiables

1. **No experimental data before 13 Nov 2026.** Code written before the sprint is fine and
   must be marked preexisting in the README and the report. Collected *results* before the
   sprint are a different thing and create a disclosure problem. The pilot is capped at ~30
   calls and is disclosed.
2. **Never mutate raw responses.** `data/raw/` is append-only. All grading, parsing and
   analysis reads from it and writes elsewhere. If a parse fails, log the failure, keep the
   raw text.
3. **The runner must be resumable.** It will crash or hit a rate limit at 3am. It must be
   restartable without re-spending quota on completed cells. Key each cell by
   `(model, claim_id, condition, rep)` and skip what already exists on disk.
4. **Reasoning effort is fixed across all models and logged.** A reviewer flagged exactly
   this confound on a previous study. Do not let it vary by model or by condition.
5. **Do not silently change the protocol.** If something in `PREREGISTRATION.md` turns out
   to be unworkable, stop and say so. Deviations go in `DEVIATIONS.md` with a timestamp and
   a reason. Do not quietly add conditions, drop models, or reword prompts mid-run.

---

## Repo layout

```
corpus/
  claims.jsonl            # 40 claims: id, text, truth_value, domain, source_url, notes
  conditions/             # one template per condition, C0..C5
  interpreter.txt         # the scope-interpreter preamble for the countermeasure arm
src/
  build_documents.py      # claim x condition -> the document the model sees
  runner.py               # dispatch, retry, resume, rate-limit handling
  providers/
    groq.py
    gemini.py
  grade.py                # deterministic metrics + LLM-judge for free-text
  analyse.py              # comparisons, Holm correction, figures
data/
  raw/                    # append-only model responses (jsonl, one file per model)
  graded/
  figures/
PREREGISTRATION.md
DEVIATIONS.md
README.md
```

---

## Build order

Build in this order. Do not start a later step to "unblock" an earlier one.

1. `corpus/claims.jsonl` — 40 claims (see pre-registration §3 for the spec).
2. `corpus/conditions/` — six document templates. This is the fiddliest part; do it early
   and eyeball every rendered output by hand before trusting it.
3. `src/build_documents.py` — deterministic, pure, unit-tested. Given a claim and a
   condition it returns exactly the text the model will see. No randomness.
4. `src/runner.py` — see constraints below.
5. `src/grade.py` — deterministic metrics first, LLM judge second.
6. `src/analyse.py` — write it against **synthetic fake data** so it runs the moment real
   data lands. Do not wait for real results to discover the analysis is broken.
7. Pilot: 5 claims, all conditions, one Groq model and one Gemini model, end to end.

---

## Provider constraints

**Groq** (free tier) — core models, generous limits:
- `openai/gpt-oss-120b`
- `openai/gpt-oss-20b`
- `qwen/qwen3.8-27b`

**Google AI Studio** (free tier). RPD quotas reset at **midnight Pacific ≈ 13:30 IST**, and
limits are per *project*, not per API key — extra keys buy nothing.
- `gemini-3.1-flash-lite` — 15 RPM / 250K TPM / **500 RPD**
- `gemini-3.5-flash-lite` — 15 RPM / 250K TPM / **500 RPD**
- `gemini-3.6-flash` — 5 RPM / 250K TPM / **20 RPD** — spot-check tier only, 60 calls total

The runner must:
- read per-model RPM/RPD from a config block, not hardcode them
- back off on 429 and distinguish per-minute from per-day exhaustion (per-day means stop
  that model until reset, not retry in a loop)
- checkpoint after every response
- print a live count of cells completed / remaining per model

Start the Gemini arm **Friday afternoon right after the reset**, not Sunday.

---

## Output contract

Every model call returns strict JSON. This is what makes grading affordable — most metrics
become exact matching rather than LLM judgment.

```json
{
  "accept": "true" | "false" | "uncertain",
  "confidence": 0,
  "reasons": ["prior_knowledge", "document_signature", ...],
  "justification": "one to three sentences"
}
```

`reasons` is a closed enum (pre-registration §5). Only `justification` needs a judge.

Use each provider's structured-output / JSON mode. On a parse failure: retry once, then log
the cell as `parse_failed` with the raw text and move on. Report the parse-failure rate per
model in the paper.

---

## Sampling

- Temperature **0.7**, 3 repetitions per cell. At temperature 0 the three reps would be
  identical and two-thirds of the quota wasted.
- Fixed seed where the provider supports it; log it either way.
- Condition order and claim order randomised per model run, logged.
- The mark always appears in the same position relative to the claim across conditions —
  position is held constant, not varied. Note this as a limitation rather than fixing it
  mid-sprint.

---

## Budget and cut order

Main run: 40 claims × 6 conditions × 3 reps = **720 calls per model**.
Core three on Groq = 2,160. Two Gemini Flash Lites = 1,440. Spot check = 60.
Countermeasure arm (C1 and C2, core models only) = 720.

If quota bites, cut in this order and record it in `DEVIATIONS.md`:

1. Countermeasure arm narrows to C1 only
2. Drop `gemini-3.5-flash-lite`
3. Reps 3 → 2
4. **Never** cut the real-obscure half of the corpus, and never cut C0 — the baseline is
   load-bearing for the analysis.

---

## Writing the report

8 pages max before references and appendices. Abstract 150–250 words. Official template
from the sprint's Guidelines tab. A **Limitations and Dual-Use / Ethical Considerations
appendix is required** and must state plainly that the failure mode described needs no
forgery, and that it is published because the mandates are landing now and the mitigation
is cheap.

Report the countermeasure result whichever way it comes out. A countermeasure that fails to
close the gap is a more interesting finding than one that works.
