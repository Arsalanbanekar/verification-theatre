# Status

Last updated 9 Nov 2026, before any data. Sprint 13–15 Nov 2026; build freeze Wed 11 Nov.
No study model has been queried. Next: the pilot (`RUNBOOK.md` §4), then the freeze.

## Done

- **Pre-registration rev 3.2** (`a56281d`): four models, temperature and reasoning stated, judge
  specified. Revision history in §12.
- **Corpus**: 40 claims in 20 twin pairs (10 real-obscure, verified verbatim; 10 invented,
  mirroring them cell by cell). Each half has 5 number and 5 date alterations. Invented names
  are clean in both passes of `corpus/screen_names.py`. Probes: `corpus/*_probe.json`.
- **Conditions** C0–C5 (`corpus/conditions/`): crJSON views checked against C2PA 2.4 and
  crJSON 2.4, with simplifications in each template's `_notes`.
- **Builder** `src/build_documents.py`: exact messages per (claim, condition, interpreter).
- **Runner** `src/runner.py`, `src/providers/`, `models.yaml`. It is resumable and paced from
  config. On HTTP 429 it waits for per-minute limits and stops a model for per-day limits. HTTP 498
  is retried; `blocked_api_access` stops Groq. Live cost per model, a $4.50 hard stop, y/n before
  spending, `--pilot`, `--dry-run`.
- **Grading** `src/grade.py`, `src/judge.py`: deterministic metrics; the Gemma judge (resumable,
  paced, blind); blind hand-label CSVs; weighted kappa, overall and per family.
- **Analysis** `src/analyse.py`: the §7 tests, four figures, and text for all 27 slots in
  `REPORT_DRAFT.md`. Checked on synthetic data (`src/synthetic.py`).
- **RUNBOOK.md** (the sprint without AI help) and **DEVIATIONS.md** (empty log, plus the
  analysis details fixed before data).
- **Tests**: 441 passing, offline (`python -m pytest -q`).

## Key decisions

- Signer: Vellumworth Document Services Ltd; certificate issuer Kestrelmoor Trust Services Ltd.
  Both are invented and screened, and identical everywhere. C4 changes only trust-list status.
- Statement: custom assertion `com.vellumworth.statement` (schema.org Claim), because
  `c2pa.metadata` cannot hold free text. C2 lists it in `gathered_assertions`, C3 in
  `created_assertions`. C5 adds the `source_quote` as a `schema:Quotation`, with no URL.
- Hashes and IDs derive from the pair id, so twins and conditions differ only where intended.
- Models (rev 3.2):
  - gpt-oss-120b, gpt-oss-20b and qwen3.8-27b on Groq: full design plus the interpreter arm.
  - gemini-3.5-flash-lite: full design. 3,600 calls in all.
- Reasoning: the lowest documented setting per model, logged per call: gpt-oss `low` (cannot be
  disabled), Qwen `none`, Gemini `MINIMAL`. Temperature 0.7 for all four.
- Budget: the $4.50 hard stop counts measured spend in `data/raw` and `data/pilot`. The dry run
  projects $3.23 on the estimate basis, about 80% of it qwen; the pilot replaces the estimate with
  measured tokens.
- Judge: `gemma-4-31b-it`, replying in plain text (JSON mode is undocumented for Gemma). Pass
  rule: 9 of 10 valid scores in the pilot. If it fails, the scores come from 150 hand-labels.
- Analysis: paired t-tests over pairs, Holm over the eight primary tests, with the permutation
  test as a robustness check. Every pre-data choice is listed in `DEVIATIONS.md`.

## Open issues: decide before the freeze

1. **Run the pilot**: `python src/runner.py --pilot`, then act on the report (`RUNBOOK.md` §4).
2. **Review the pre-data analysis choices** in `DEVIATIONS.md`, especially the H3 threshold
   (fewer than half of credential mentions scored 2) and the t-test as primary.
3. **Power.** There are 10 real-obscure pairs and Holm runs over 8 tests, so only clear effects
   reach significance. Elsewhere the CIs carry the result, and the generated text says so.
4. **qwen/qwen3.8-27b is a preview model.** Run `--check-models` just before the sprint.
5. **Gemma judge limits are undocumented.** `models.yaml` paces it conservatively (15 RPM,
   15K TPM, 1,000 RPD).
6. **`REPORT_DRAFT.md`** still names rev 3.1 and the dropped Gemini models.
   `results_summary.md` lists every line to update.

## File map

| Path | Contents |
|---|---|
| `PREREGISTRATION.md`, `DEVIATIONS.md` | The plan; departures from it and pre-data choices |
| `RUNBOOK.md`, `REPORT_DRAFT.md` | How to run the sprint; the report draft |
| `corpus/` | Claims, condition templates, signer, probes, rendered examples |
| `src/build_documents.py`, `src/prompt_text.py`, `src/output_schema.py` | Prompts and parsing |
| `src/runner.py`, `src/providers/`, `models.yaml` | Dispatch, limits, retries, cost, resume |
| `src/judge.py`, `src/grade.py`, `src/analyse.py` | Judge, grading, analysis |
| `data/raw/`, `data/pilot/` | Append-only responses (created by the runner) |
| `data/graded/`, `data/human/`, `data/results/`, `data/logs/` | Derived files and logs |

## How to run

See `RUNBOOK.md`: the pilot and freeze, then from 13 Nov `runner.py`, `grade.py --judge`,
hand-labels, and `analyse.py`.
