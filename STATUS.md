# Status

Last updated 8 Nov 2026, before any data. Sprint 13–15 Nov 2026; build freeze Wed 11 Nov.
No study model has been queried.

## Done

- **Pre-registration rev 3.1** (`62535a8`); revision history in §12.
- **Corpus**: 40 claims in 20 twin pairs (10 real-obscure, verified verbatim; 10 invented,
  mirroring them cell by cell). Each half has 5 number and 5 date alterations. Invented names
  are clean in both passes of `corpus/screen_names.py`. Probes: `corpus/*_probe.json`.
- **Conditions** C0–C5 (`corpus/conditions/`): crJSON views checked against C2PA 2.4 and
  crJSON 2.4, with simplifications in each template's `_notes`.
- **Builder** `src/build_documents.py`: exact messages per (claim, condition, interpreter).
- **Runner** `src/runner.py` + `src/providers/` + `models.yaml`. The dry run plans 4,380 calls.
- **Tests**: 393 passing (`python -m pytest`).

## Key decisions

- Signer: Vellumworth Document Services Ltd; certificate issuer Kestrelmoor Trust Services Ltd.
  Both invented and screened. Identical everywhere; C4 changes only trust-list status.
- Statement: custom assertion `com.vellumworth.statement` (schema.org Claim), because
  `c2pa.metadata` cannot hold free text. C2 lists it in `gathered_assertions`, C3 in
  `created_assertions`. C5 adds the `source_quote` as a `schema:Quotation`, with no URL, so
  real and invented items have the same structure.
- Hashes and IDs derive from the pair id, so twins and conditions differ only where intended.
- Reasoning: the lowest documented setting per model, logged per call. gpt-oss `low` (cannot
  be disabled), Qwen `none`, Gemini `MINIMAL`. Not identical in kind across providers.
- gemini-3.6-flash: temperature not sent; the provider ignores it and has deprecated it.
- Spot check (gemini-3.6-flash): pairs real-01, real-03, real-10, inv-01 and inv-06
  (seed 20261113), C0/C1 × 3.
- Manifest JSON is printed with 2-space indents. Compact JSON would cut about 20% of tokens.

## Open issues: decide before the freeze

1. **Groq quota.** Documented limits are 8K TPM and 200K TPD per model. At ~1,950 tokens per
   call that is ~9.4 days per Groq model. Check console.groq.com/settings/limits; if real, use
   a paid tier or the CLAUDE.md cut order.
2. **qwen/qwen3.8-27b is a preview model** ("may be discontinued at short notice").
   Run `--check-models` just before the sprint.
3. **Prereg §6 vs providers.** "Temperature 0.7" cannot apply to gemini-3.6-flash, and
   "reasoning effort identical" cannot be literal across providers. Candidates for DEVIATIONS.md.
4. **gemini-3.1-flash-lite** thinking levels are undocumented; the pilot must confirm MINIMAL.
5. **Pilot size.** CLAUDE.md asks for 5 claims × all conditions × 2 models (60 calls) but caps
   the pilot at ~30 calls.
6. **Gemini 429 format** for generateContent is undocumented. Check the events log in the pilot.

## File map

| Path | Contents |
|---|---|
| `PREREGISTRATION.md`, `CLAUDE.md`, `README.md` | Design; build notes; overview |
| `corpus/claims.jsonl` | The 40 claims |
| `corpus/conditions/` | Templates C0–C5, `signer.json` |
| `corpus/rendered_examples/` | Exact prompts for inv-03-t and real-03-t |
| `src/build_documents.py`, `src/prompt_text.py` | Builder; fixed wording |
| `src/output_schema.py` | JSON schema and response parser |
| `src/runner.py`, `src/providers/`, `models.yaml` | Dispatch, limits, retries, resume |
| `tests/` | Builder, prompt and runner tests (offline) |
| `data/raw/{model}.jsonl` | Append-only responses (created by the runner) |
| `data/logs/` | Events, cell order, run log |

## How to run

`pip install -r requirements.txt`; copy `.env.example` to `.env` and add the keys.
`python src/runner.py --dry-run` / `--check-models` / no flags for the full run (resumable).
Pilot: `--models gpt-oss-120b,gemini-3.1-flash-lite --claims <ids> --reps 1 --out-dir data/pilot`.

## Next steps

5. `src/grade.py`; 6. `src/analyse.py` on synthetic data; 7. pilot; 8. freeze.
