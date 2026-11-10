# Verification Theatre

A pre-registered study for the Apart Research **AI x Epistemics Research Sprint**
(13–15 November 2026), Track 2: Trust Infrastructure.

When a document carries a C2PA / Content Credentials provenance mark, do language models
respond to what the mark actually certifies, or merely to the fact that a mark is present?
The hypotheses, design, measures and analysis plan are in
[PREREGISTRATION.md](PREREGISTRATION.md).

## Status

**Data collection began on 10 November 2026, before the sprint.** The pre-registration (rev
3.3), the corpus, the code and the analysis were committed first. Collection starts with a
pilot, then the main run (the three Groq models, then Gemini), then the two judges. After the
pilot, and before the main run, the scope-accuracy judge was replaced (pre-registration rev 3.4,
§12). Every response in `data/raw/` and `data/pilot/` records when it was collected, and those
timestamps are never altered.

## Work that predates the sprint

The sprint starts on 13 November 2026. Everything in this repository before then is pre-sprint
work, including the data, and the git history dates each file. In particular:

- **Commit `69f332f`** (8 November 2026): the pre-registration (revision 2), the build
  notes in `CLAUDE.md`, five draft corpus claims, and `corpus/screen_names.py`.
- **`corpus/screen_names.py`** (written 6 November 2026): screens invented names against
  the GeoNames gazetteer, rejecting any within edit distance 2 of a real place
  (pre-registration §3).
- **The corpus, condition templates and code** (6–11 November 2026): `corpus/`, `src/`,
  `tests/`, `models.yaml`, `RUNBOOK.md`, and the pre-sprint sections of `REPORT_DRAFT.md`.
- **Tests and decision rules** (9–10 November 2026, before any data): `PREREGISTRATION.md` §7,
  revision 3.3.
- **The pilot**: 20 study calls on one claim (`real-01-t`) and a 10-call format check of the
  scope-accuracy judge. Its data and report are in `data/pilot/`, dated inside
  `pilot_report.md`. Pilot data is excluded from every analysis.
  - The first run also made 4 calls to the original judge, `gemma-4-31b-it`, which proved too
    slow and unreliable. Rev 3.4 replaced it.
  - Those judgements stay in `data/pilot/judge.jsonl` and are never read.
- **Pre-registration rev 3.4** (decided 10 November 2026, after the pilot; committed 11 November,
  before the main run). It adds:
  - a paid OpenRouter judge, chosen by stated criteria;
  - a free cross-check judge from another family;
  - a rule that judge results are reported only if the two agree (weighted kappa of at least
    0.6).

  It also removes the hand-labels.
- **The main data** (`data/raw/`), collected from 10 November 2026 with the frozen code. The
  first and last collection times are reported in `data/results/results_summary.md` and in the
  report.

At the freeze, the code is tagged `sprint-freeze` (RUNBOOK.md §5), so the version that collected
the data can be checked out exactly.

## Repository

| Path | Contents |
|---|---|
| `PREREGISTRATION.md` | Hypotheses, conditions, measures, analysis plan (rev 3.4) |
| `DEVIATIONS.md` | Changes made after data collection began |
| `RUNBOOK.md` | How the study is run, step by step, from pilot to submission |
| `REPORT_DRAFT.md` | Report draft with slots that `src/analyse.py` fills |
| `CLAUDE.md` | Build instructions for the codebase |
| `STATUS.md` | Progress, decisions, open issues |
| `corpus/claims.jsonl` | Claim corpus: true/false twin pairs, invented and real-obscure |
| `corpus/screen_names.py` | Near-collision screen for invented names |
| `corpus/*_probe.json` | Closed-book corpus probes run on a model outside the study |
| `corpus/conditions/` | Condition templates C0–C5 and the shared signer |
| `corpus/rendered_examples/` | Exact prompts for two claims |
| `models.yaml` | Models, limits, prices, budget and the two judges |
| `src/build_documents.py`, `src/prompt_text.py` | The exact prompt for each claim and condition |
| `src/runner.py`, `src/providers/` | Resumable, rate-limited study calls (Groq, Gemini) and judge calls (OpenRouter); pilot; dry run |
| `src/judge.py`, `src/grade.py` | Metrics, the two blind scope-accuracy judges, their agreement (kappa) |
| `src/analyse.py` | Pre-registered tests, figures, results summary |
| `src/synthetic.py` | Fake data for tests and rehearsal |
| `tests/` | Offline tests |
| `data/` | Responses (append-only), grades, results; created by the scripts |
