# Verification Theatre

A pre-registered study for the Apart Research **AI x Epistemics Research Sprint**
(13–15 November 2026), Track 2: Trust Infrastructure.

When a document carries a C2PA / Content Credentials provenance mark, do language models
respond to what the mark actually certifies, or merely to the fact that a mark is present?
The hypotheses, design, measures and analysis plan are in
[PREREGISTRATION.md](PREREGISTRATION.md).

## Status

Pre-registered (rev 3.4). The design, corpus, code and pre-registration were prepared before the
sprint, together with a small pilot excluded from all analysis. The repository as it stood then
is tagged `pre-sprint`. Main data collection, judging, analysis and write-up happen during the
sprint (13–15 November 2026). Every response in `data/raw/` and `data/pilot/` records when it
was collected, and those timestamps are never altered.

## Pre-sprint vs sprint work

The git history dates every file.

**Before the sprint (preexisting)**

- **All code**, written 8–11 November 2026: `src/`, `tests/`, `models.yaml` and `RUNBOOK.md`.
  `corpus/screen_names.py`, which screens invented names against the GeoNames gazetteer
  (pre-registration §3), was written on 6 November.
- **The corpus**: 20 true/false twin pairs in `corpus/claims.jsonl` (`5bcdcc3`, 8 November),
  and the condition templates C0–C5 with the shared signer (`33be828`, 8 November).
- **Both probes**: `corpus/obscurity_probe.json` and `corpus/realness_probe.json` (`5bcdcc3`,
  8 November). Each is a closed-book run on a model outside the study.
- **The pre-registration**, `PREREGISTRATION.md`, revisions 1 to 3.4:

  | Rev | Date | Commit |
  |---|---|---|
  | 1 | 6 November | Not committed; the repository starts at rev 2. §12 summarises it. |
  | 2 | 7 November | `69f332f` (committed 8 November) |
  | 3 | 8 November | `e51bab1` |
  | 3.1 | 8 November | `62535a8` |
  | 3.2 | 9 November | `a56281d` |
  | 3.3 | 10 November | `6e3d9e3`; H3 tightened in `8b17a42` |
  | 3.4 | Decided 10 November after the pilot's first run; committed 11 November | `8d4f9fa` |

- **A pilot of the study calls**, on 10–11 November (`data/pilot/`), excluded from all analysis.
  - 20 cells on one claim (`real-01-t`): 17 on 10 November, and Qwen's last 3 on 11 November.
  - The 10 November run also made 4 calls to the original judge, `gemma-4-31b-it`. It proved
    too slow and unreliable, and rev 3.4 replaced it. Those judgements stay in
    `data/pilot/judge.jsonl` and are never read.
- **The pre-sprint sections of `REPORT_DRAFT.md`**, marked *(pre-sprint)*.

**During the sprint (13–15 November)**

- **Main data collection**: the three Groq models, then Gemini, into `data/raw/`, run with the
  code at tag `pre-sprint`. The first and last collection times are given in
  `data/results/results_summary.md` and in the report.
- **Judging**: the two judges are chosen, the pilot's judge check runs, then the judges score
  the main data (`data/graded/`).
- **Analysis** (`data/results/`) **and the write-up.**

On 13 November, before any of this, timing statements were corrected:
- in the documentation;
- in `PREREGISTRATION.md` (`172861e`, no design change);
- in one sentence of the results summary that `src/analyse.py` writes.

The pilot data and a pointer in `DEVIATIONS.md` were committed the same day, before the tag.
Any later change to the code or protocol is listed in `DEVIATIONS.md`.

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
