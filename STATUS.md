# Status

Last updated 11 Nov 2026. Data collection started on 10 Nov 2026, before the sprint (13–15 Nov
2026), in this order:
1. the pilot;
2. the freeze;
3. the Groq models, then Gemini;
4. the two judges (`RUNBOOK.md` §4–10).

Pilot: 17 of 20 study calls done; Qwen's C2, C5 and C2-with-interpreter remain. Finish them with
`python src/runner.py --pilot --skip-judge`. The pilot's judge check waits for the new judge.
Gemma (the judge in rev 3.2–3.3) was too slow and unreliable in the pilot and was replaced in
rev 3.4. Its 4 pilot judgements stay in `data/pilot/judge.jsonl` and are never read.

## Done

- **Pre-registration rev 3.4** (after the pilot, before the main run): two OpenRouter judges and
  the kappa gate (§5); H3 when the gate fails (§7); judge limitations (§9). Rev 3.3 (§7) holds the
  tests and decision rules; revision history in §12.
- **Corpus**: 40 claims in 20 twin pairs (10 real-obscure, verified verbatim; 10 invented,
  mirroring them cell by cell). Each half has 5 number and 5 date alterations. Invented names
  are clean in both passes of `corpus/screen_names.py`. Probes: `corpus/*_probe.json`.
- **Conditions** C0–C5 (`corpus/conditions/`): crJSON views checked against C2PA 2.4 and
  crJSON 2.4, with simplifications in each template's `_notes`.
- **Builder** `src/build_documents.py`: exact messages per (claim, condition, interpreter).
- **Runner** `src/runner.py`, `src/providers/`, `models.yaml`:
  - resumable, and paced from config;
  - HTTP 429: waits for per-minute limits, stops a model for per-day limits;
  - retries HTTP 498 and Groq `json_validate_failed`;
  - live cost and a $4.50 hard stop;
  - `--pilot` (`--skip-judge`), `--dry-run`.
- **Judges** `src/judge.py`, `src/grade.py`, `src/providers/openrouter.py`: blind, concurrent and
  resumable.
  - Every attempt is logged.
  - The §5 criteria are checked from `models.yaml`.
  - The cross-check has a hard stop at 48 calls per UTC day and resumes across days.
  - Agreement is weighted kappa, overall and per family, with the gate.
- **Analysis** `src/analyse.py`: the §7 tests, the rev 3.4 gate, four figures, and text for all
  27 slots in `REPORT_DRAFT.md`, whose facts are current (rev 3.4). Checked on synthetic data.
- **RUNBOOK.md** (the whole run without AI help) and **DEVIATIONS.md** (empty).
- **Tests**: 511 passing, offline (`python -m pytest -q`).

## Key decisions

- Signer: Vellumworth Document Services Ltd; certificate issuer Kestrelmoor Trust Services Ltd.
  Both are invented and screened, and identical everywhere. C4 changes only trust-list status.
- Statement: custom assertion `com.vellumworth.statement` (schema.org Claim), because
  `c2pa.metadata` cannot hold free text. C2 lists it in `gathered_assertions`, C3 in
  `created_assertions`. C5 adds the `source_quote` as a `schema:Quotation`, with no URL.
- Models (rev 3.2): gpt-oss-120b, gpt-oss-20b, qwen3.8-27b (Groq; full design plus the
  interpreter arm); gemini-3.5-flash-lite (full design). 3,600 calls in all.
- Reasoning: the lowest documented setting per model, logged per call (gpt-oss `low`, Qwen
  `none`, Gemini `MINIMAL`). Temperature 0.7 for all four.
- Budget: the $4.50 hard stop covers study calls; each judge has its own `budget_usd`.
- Judges (rev 3.4). Neither may come from OpenAI/gpt-oss, Qwen/Alibaba or Google.
  - Main: a paid OpenRouter model, the strongest reasoning model under about $2 for 600
    judgements, with its provider pinned.
  - Cross-check: a `:free` model from a third family, scoring 100 of the 600.
  - Judge results are reported only if the weighted kappa is at least 0.6; otherwise H3 is not
    tested and enters Holm with p = 1. No human labels.
- Analysis (§7): paired t-tests over pairs, Holm over the eight primary tests, and permutation
  tests as a robustness check. H3 needs the 95% CI's upper bound for score 2 below 0.5 and
  p_holm < .05.

## Open issues

1. **Finish the pilot's study calls**: `python src/runner.py --pilot --skip-judge`.
2. **Choose the judges** once OpenRouter has credit. The top 3 candidates for each come with
   prices, then the choice goes in `models.yaml` and is committed (`RUNBOOK.md` §9a). After that
   comes the pilot judge check.
3. **Cross-check time**: 48 calls per UTC day means three UTC days for 100. It starts only after
   the main run.
4. **Pre-sprint data.** `CLAUDE.md` still says "No experimental data before 13 Nov 2026".
   `PREREGISTRATION.md` line 3 says changes after data exist go in `DEVIATIONS.md`; rev 3.4
   follows the pilot, and §12 records that. The README and the report must disclose the dates.
5. **Power.** With 10 real-obscure pairs and Holm over 8 tests, only clear effects reach
   significance. Elsewhere the CIs carry the result, and the generated text says so.
6. **qwen/qwen3.8-27b is a preview model.** Run `--check-models` just before the main run.

## File map

| Path | Contents |
|---|---|
| `PREREGISTRATION.md`, `DEVIATIONS.md` | The plan and its tests; changes after data collection began |
| `RUNBOOK.md`, `REPORT_DRAFT.md` | How to run the sprint; the report draft |
| `corpus/` | Claims, condition templates, signer, probes, rendered examples |
| `src/build_documents.py`, `src/prompt_text.py`, `src/output_schema.py` | Prompts and parsing |
| `src/runner.py`, `src/providers/`, `models.yaml` | Dispatch, limits, retries, cost, resume |
| `src/judge.py`, `src/grade.py`, `src/analyse.py` | Judges, grading, agreement, analysis |
| `data/raw/`, `data/pilot/` | Append-only responses (created by the runner) |
| `data/graded/`, `data/results/`, `data/logs/` | Grades and judge calls, results, logs |
