# Verification Theatre

A pre-registered study for the Apart Research **AI x Epistemics Research Sprint**
(13–15 November 2026), Track 2: Trust Infrastructure.

When a document carries a C2PA / Content Credentials provenance mark, do language models
respond to what the mark actually certifies, or merely to the fact that a mark is present?
The hypotheses, design, measures and analysis plan are in
[PREREGISTRATION.md](PREREGISTRATION.md).

## Status

**No experimental data has been collected.** No study model has been queried, and data
collection does not begin until 13 November 2026. The corpus, code and analysis are complete
and tested offline. A 30-call pilot, disclosed below, runs before the sprint.

## Work that predates the sprint

The sprint starts on 13 November 2026. Everything in this repository before then is pre-sprint
work, and the git history dates each file. In particular:

- **Commit `69f332f`** (8 November 2026): the pre-registration (revision 2), the build
  notes in `CLAUDE.md`, five draft corpus claims, and `corpus/screen_names.py`.
- **`corpus/screen_names.py`** (written 6 November 2026): screens invented names against
  the GeoNames gazetteer, rejecting any within edit distance 2 of a real place
  (pre-registration §3).
- **The corpus, condition templates and code** (6–11 November 2026): `corpus/`, `src/`,
  `tests/`, `models.yaml`, `RUNBOOK.md`, and the pre-sprint sections of `REPORT_DRAFT.md`.
- **Pre-data analysis choices** (9 November 2026): listed in `DEVIATIONS.md`.
- **The pilot**: 20 study calls on one claim (`real-01-t`) and 10 calls to the
  scope-accuracy judge, run before the sprint to check the pipeline and the judge's
  pre-registered pass rule. Its data and report are in `data/pilot/`, dated inside
  `pilot_report.md`. Pilot data is excluded from every analysis.

At the freeze, the code is tagged `sprint-freeze` (RUNBOOK.md §5), so the version that collected
the data can be checked out exactly.

## Repository

| Path | Contents |
|---|---|
| `PREREGISTRATION.md` | Hypotheses, conditions, measures, analysis plan (rev 3.2) |
| `DEVIATIONS.md` | Deviations from the plan, and analysis details fixed before any data |
| `RUNBOOK.md` | How the study is run, step by step, from pilot to submission |
| `REPORT_DRAFT.md` | Report draft with slots that `src/analyse.py` fills |
| `CLAUDE.md` | Build instructions for the codebase |
| `STATUS.md` | Progress, decisions, open issues |
| `corpus/claims.jsonl` | Claim corpus: true/false twin pairs, invented and real-obscure |
| `corpus/screen_names.py` | Near-collision screen for invented names |
| `corpus/*_probe.json` | Closed-book corpus probes run on a model outside the study |
| `corpus/conditions/` | Condition templates C0–C5 and the shared signer |
| `corpus/rendered_examples/` | Exact prompts for two claims |
| `models.yaml` | Models, limits, prices, budget and the judge |
| `src/build_documents.py`, `src/prompt_text.py` | The exact prompt for each claim and condition |
| `src/runner.py`, `src/providers/` | Resumable, rate-limited study calls; pilot; dry run |
| `src/judge.py`, `src/grade.py` | Metrics, the blind scope-accuracy judge, hand-labels, kappa |
| `src/analyse.py` | Pre-registered tests, figures, results summary |
| `src/synthetic.py` | Fake data for tests and rehearsal |
| `tests/` | Offline tests |
| `data/` | Responses (append-only), grades, results; created by the scripts |
