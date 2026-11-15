# Runbook: running the sprint without AI help

Everything from the pilot to submission, in order. Run every command from the repository folder
in a terminal (VS Code: *Terminal → New Terminal*). Times are IST. Each step says what you should
see; section 12 lists what can go wrong and what to do.

## Contents

1. [Rules that hold throughout](#1-rules-that-hold-throughout)
2. [Setup check](#2-setup-check-once-before-the-pilot)
3. [Rehearsal on synthetic data](#3-rehearsal-on-synthetic-data-no-api-calls)
4. [The pilot](#4-the-pilot-first)
5. [Freeze: the `pre-sprint` tag](#5-freeze-the-pre-sprint-tag)
6. [Timeline](#6-timeline)
7. [Main run: Groq, then Gemini](#7-main-run-groq-then-gemini)
8. [Gemini, second quota day](#8-gemini-second-quota-day)
9. [The judge: choosing, checking, judging](#9-the-judge-choosing-checking-judging)
10. [The §5 agreement gate: cannot be evaluated](#10-the-5-agreement-gate-cannot-be-evaluated)
11. [Analysis](#11-analysis)
12. [Failure modes and fixes](#12-failure-modes-and-fixes)
13. [Filling REPORT_DRAFT.md](#13-filling-report_draftmd)
14. [Submission checklist](#14-submission-checklist)
15. [Appendix: cut order, logs, status commands](#15-appendix-cut-order-logs-status-commands)

---

## 1. Rules that hold throughout

- **Pre-sprint vs sprint work.** The sprint runs 13–15 Nov 2026.
  - Before it: the code, the corpus, both probes, the pre-registration (revs 1–3.4) and a pilot
    of the study calls (10–11 Nov, section 4). The pilot is disclosed and excluded from analysis.
  - During it: main data collection, judging, analysis and write-up.

  The README's "Pre-sprint vs sprint work" section says so, and the report gives the collection
  dates (section 13).
- **The judge is chosen before any main-data judging** (pre-registration §5, rev 3.4): its model
  ID, family and serving provider go into `models.yaml` and are committed on their own before
  `grade.py --judge` first runs (section 9). Since 15 Nov 2026 that is one judge, glm-5.2 on
  Adaption, with no cross-check (`DEVIATIONS.md`).
- **Never edit, move or delete anything in `data/raw/`, `data/pilot/` or `data/logs/`, and
  never alter a timestamp.** The scripts only append, and every response records when it was
  collected. A torn last line after a crash is skipped automatically.
- **Do not change the protocol once the main run starts.** That covers prompts, conditions,
  models, temperature, reasoning settings and reps. If something must change, first write an
  entry in `DEVIATIONS.md` (time, what, why), then change it. Pacing limits (`rpm`, `tpm`, `rpd`
  in `models.yaml`) are not protocol and can be adjusted.
- **Commit after each stage; push only when you decide to publish.** No step below depends
  on pushing.
- **Every command is safe to re-run.** The runner skips finished cells and the judge skips
  judged responses. When in doubt, re-run the same command.
- **No uncommitted changes to tracked files while the runner runs.** Each response records the
  git commit, marked `-dirty` if the working tree has changes.
- Keep the laptop plugged in and stop it sleeping (*Settings → System → Power → Screen and
  sleep → Never*) while anything is running.

## 2. Setup check (once, before the pilot)

```
pip install -r requirements.txt
python -m pytest -q
```
You should see a final line like `511 passed in 240s`: no `failed` and no `error`.

Check that the keys are present, without printing them:
```
python -c "import pathlib; print(sorted(l.split('=')[0] for l in pathlib.Path('.env').read_text().splitlines() if '=' in l and l.split('=',1)[1].strip()))"
git check-ignore .env
```
You should see `['ADAPTION_API_KEY', 'GEMINI_API_KEY', 'GROQ_API_KEY']`, then `.env` (git ignores
it). `ADAPTION_API_KEY` is needed only for the judge (section 9). The pre-registered OpenRouter
judges, and so `OPENROUTER_API_KEY`, were replaced on 15 Nov 2026 (`DEVIATIONS.md`).

```
python src/runner.py --check-models
```
You should see:
```
gemini: gemini-3.5-flash-lite        available
groq: openai/gpt-oss-120b          available
groq: openai/gpt-oss-20b           available
groq: qwen/qwen3.8-27b             available
```
The judge is not listed here; the pilot's judge check exercises it (section 4).

```
python src/runner.py --dry-run
```
This makes no API calls. You should see:
```
model                  planned   done to run ~tok/call  ~days  spent $  ~$ left  basis
gpt-oss-120b               960      0    960      1775   0.00    0.000    0.428  estimate
gpt-oss-20b                960      0    960      1775   0.00    0.000    0.214  estimate
qwen3.8-27b                960      0    960      1775   0.00    0.000    2.592  estimate
gemini-3.5-flash-lite      720      0    720      1694   1.44    0.000    0.000  estimate
TOTAL                     3600      0   3600                     0.000    3.235
Projected total spend $3.23 (already spent $0.000); hard stop $4.50.
```
`estimate` means 400 output tokens per call are assumed. After the pilot, the basis becomes
`measured` and the numbers change.

## 3. Rehearsal on synthetic data (no API calls)

This takes five minutes and is worth doing once. It runs the whole grading and analysis
pipeline on fake data with built-in effects, so you see the real outputs before real data
exists.
```
python src/synthetic.py --seed 2 --out data/synthetic/raw --graded-dir data/synthetic/graded
python src/analyse.py --raw-dir data/synthetic/raw --graded-dir data/synthetic/graded --pilot-dir data/synthetic/pilot --out data/synthetic/results
```
The last lines should be:
```
results -> data\synthetic\results
  scope-accuracy source: judge (the judges' weighted kappa is 0.87 on 79 responses, at least 0.6: judge results are reported); 28 draft slots filled automatically, 0 need a hand fill
```
Open `data/synthetic/results/results_summary.md`, `REPORT_DRAFT.filled.md` and the four PNGs.
The fake data raises acceptance in C1–C4, separates the twins in C5, and has the interpreter
cut acceptance. Fake scores come from two judges, agreeing 90% of the time: the rehearsal still
fakes the cross-check to exercise the agreement code. The real run has no cross-check
(`DEVIATIONS.md`, 15 Nov 2026), so its scope-accuracy source is `exploratory` (section 11). `data/synthetic/` is
git-ignored; delete it whenever you like.

## 4. The pilot (first)

The pilot has two stages: the study calls now, and the judge check once the main judge is chosen
(section 9a).

**Stage 1: study calls.**
```
python src/runner.py --pilot --skip-judge
```
- Each model answers claim `real-01-t` in C0, C1, C2 and C5.
- Each also answers one extra cell: C2 with the interpreter for the three Groq models, C4 for
  Gemini.

That is 20 cells. Finished cells are never asked again, so a re-run makes only the missing calls.
Everything goes to `data/pilot/`, which the analysis never reads. Cost is about $0.02; time is
a few minutes. It starts with
`PILOT: 20 study cells on real-01-t, N still to run; then no judge calls (--skip-judge). Output: data\pilot`,
prints the report, and ends with
`Judge check skipped. Once the main judge is set in models.yaml, ...`.

Without `--skip-judge`, the pilot refuses to start while the main judge is not chosen. It makes
no call and prints:
`The pilot's judge check needs the main judge, which cannot run yet`.

Stage 1 is done, before the sprint: 17 study calls on 10 Nov 2026 and Qwen's last 3 on 11 Nov.
Qwen's C2 ended `parse_failed` after its retry. `data/pilot/judge.jsonl` holds 4 judgements by
the judge replaced in pre-registration rev 3.4. It stays on disk and is never read.

**Stage 2: the judge check** (after section 9a):
```
python src/runner.py --pilot
```
It repeats no study call. The main judge scores 10 of the pilot answers, round-robin over the
four models, as a format check. The rows go to `data/pilot/judge_check.jsonl`, and every attempt
goes to `data/pilot/logs/judge_check.attempts.jsonl`.

Read `data/pilot/pilot_report.md` and act on it:

| The report shows | Meaning | Do this |
|---|---|---|
| Every study row `ok` | Models return valid JSON | Nothing |
| A row `PARSE FAIL` | That call's JSON failed twice | Open `data/pilot/<model>.jsonl` and read `raw_text` and `finish_reason`. If `finish_reason` is `length`, the answer was cut off: raise that model's `max_output_tokens` in `models.yaml` before the freeze. One failure is not a blocker; parse failures are reported per model. |
| Judge check `SKIPPED` | Stage 1 only | Section 9a, then stage 2 |
| Judge check `**PASS**` (at least 9 of 10 valid) | The judge returns usable scores | Sections 9b and 9c |
| Judge check `**FAIL**` | Fewer than 9 of 10 valid scores | Pre-registration §5: correct the request (for example `json_mode` or `max_output_tokens` in `models.yaml`) or choose the next candidate. Commit the change, then run stage 2 again. A new model gets a fresh check; the old model's rows are ignored. `grade.py --judge` refuses a model whose check failed. |
| Judge check `**INCOMPLETE**` | Fewer than 10 judge calls returned (Ctrl+C, rate limits or server errors) | Re-run `python src/runner.py --pilot`. It re-asks nothing that already returned. Failed attempts are printed as `[main judge] HTTP ...`. |
| `WARNING: projected total ... above $4.00` | The full run may hit the $4.50 hard stop | Apply the cut order (section 15) before the main run and record it in `DEVIATIONS.md` |
| `Projected total including spend so far: $X` | Cost of the full run, from measured tokens (judges excluded) | Keep this number for the report |

Commit the pilot after each stage. It is disclosed data. Stage 1 was committed on 13 Nov; after
stage 2:
```
git add data/pilot
git commit -m "Pilot judge check (disclosed; excluded from analysis)"
```

## 5. Freeze: the `pre-sprint` tag

The tag `pre-sprint` (13 Nov 2026) marks everything prepared before the sprint: the code, corpus,
probes, pre-registration and the pilot's study calls. The main run uses that code. Before
starting it:
```
git status
git log --oneline -1 pre-sprint
```
`git status` should report nothing to commit. From here, no code changes. If a bug forces one,
commit it on its own with a message saying why, and add a `DEVIATIONS.md` entry.

One change is part of the protocol: filling in the judge in `models.yaml` (section 9a), which
pre-registration §5 requires before any main-data judging. Commit it on its own.

## 6. Timeline

Step 1 was done before the sprint, and step 2 on 13 Nov 2026, before the main run. Main data
collection runs during the sprint, from 13 Nov: the three Groq models, then gemini-3.5-flash-lite. The judge comes after the main
run. Since 15 Nov 2026 it is glm-5.2 on Adaption, with no cross-check (`DEVIATIONS.md`).

| Step | What | Command | Takes |
|---|---|---|---|
| 1 | Pilot study calls (done 10–11 Nov, before the sprint) | `python src/runner.py --pilot --skip-judge` | a few minutes |
| 2 | Freeze: tag `pre-sprint` (done 13 Nov) | section 5 | 2 min |
| 3 | Groq: gpt-oss-120b, gpt-oss-20b, qwen3.8-27b | `python src/runner.py --models gpt-oss-120b,gpt-oss-20b,qwen3.8-27b` | 30–90 min |
| 4 | Gemini, up to its daily quota | `python src/runner.py --models gemini-3.5-flash-lite` | ~40 min, then it stops for the day |
| 5 | Gemini's remaining cells, after the time it prints | the same command | ~20 min |
| 6 | Choose the judge and commit `models.yaml` (done 15 Nov: glm-5.2 via Adaption, `e578ba5`) | section 9a | 30 min |
| 7 | Pilot judge check (done 15 Nov: 10/10 valid, PASS, `e64307a`) | `python src/runner.py --pilot` | a few minutes |
| 8 | Main judge, once all four models are done | `python src/grade.py --judge` | 15–45 min |
| 9 | Analysis | `python src/analyse.py` | 2 min |
| 10 | Write up, check, submit | sections 13–14 | |

The pre-registered cross-check judge (100 responses scored by a second, free model) is dropped
from the run order (`DEVIATIONS.md`, 15 Nov 2026): `grade.py --crosscheck` refuses, the §5 gate
cannot be evaluated (section 10), and the analysis reports the judge's scores as exploratory
and unvalidated.

**Gemini's quota.** Gemini allows 500 calls a day, and its day resets at midnight US Pacific,
which is 13:30 IST.
- The first session uses whatever is left of the current Pacific day. The pilot's 5 Gemini
  calls count if they fell on the same Pacific day.
- Started before 13:30 IST, the first stop clears at 13:30 the same day, so Gemini can finish
  that afternoon.
- Started after 13:30 IST, Gemini finishes after 13:30 the next day.

## 7. Main run: Groq, then Gemini

**Groq first.**
```
python src/runner.py --check-models
python src/runner.py --models gpt-oss-120b,gpt-oss-20b,qwen3.8-27b
```
The runner prints the projection table for the three Groq models, then asks:
```
Start the run? Projected total spend $3.25. [y/N]
```
Your number will differ: the total includes the pilot's spend, and after the pilot the
projection uses measured tokens. Type `y` and press Enter; any other answer prints
`Not started; nothing was sent.` Then:
```
run 3f2a9c1b7d4e at <commit>: gpt-oss-120b, gpt-oss-20b, qwen3.8-27b. Ctrl+C stops cleanly.
```
and every 30 seconds:
```
[14:05:12] progress
  gpt-oss-120b            412/960  done (ok 410, parse_failed 2), 548 left | $0.183 | this run 415 calls, 41.2/min | running
  gpt-oss-20b             ...
  qwen3.8-27b             ...
  total spend on disk $0.912
```
Each model ends in the state `finished: every planned cell is done`, and then the command
returns. To stop early, press Ctrl+C once: you'll see
`Interrupted: finishing the calls in flight, then stopping.` Re-run the same command to
continue.

**Then Gemini.**
```
python src/runner.py --models gemini-3.5-flash-lite
```
Answer `y`. Gemini is free, so the projected total is the spend so far. It runs at about 15
calls a minute and stops itself at the daily quota (dates vary):
```
[gemini-3.5-flash-lite] daily limit reached (500 calls today reaches the configured RPD 500). Stopping this model; resume after 2026-11-11 00:00 Pacific = 08:00 UTC = 2026-11-11 13:30 local.
```
Google may run out first, because the pilot's calls count for Google but not for the runner.
The reason then reads `provider reports the daily quota is exhausted`. Either way, continue
with section 8 after the printed local time.

Meanwhile, take a first look (no API calls):
```
python src/grade.py
```
```
3380 completed cells -> data\graded\responses.csv
  gpt-oss-120b           cells  960  parse_failed   3 (0.0031)  retries 4  $0.39
  ...
```
3,380 is 2,880 Groq plus 500 Gemini. It is a few fewer if the pilot shared Gemini's day, or if
some cells were skipped after errors.
- Check the parse-failure rates.
- Do **not** run `--judge` yet. The judge sample is drawn once, stratified
  across all four models, so it must wait for Gemini to finish. `grade.py` refuses until then.

Commit what you have (it is append-only data):
```
git add data/raw data/logs
git commit -m "Main run: Groq complete, Gemini first quota day"
```

## 8. Gemini, second quota day

After the local time the runner printed:
```
python src/runner.py --models gemini-3.5-flash-lite
```
Answer `y`. Gemini runs its remaining cells (about 220, roughly 20 minutes) and ends with
`finished: every planned cell is done`. Confirm that nothing is left for any model:
```
python src/runner.py --dry-run
```
Every row should show `to run 0`. Then commit:
```
git add data/raw data/logs
git commit -m "Main run complete"
```

## 9. The judge: choosing, checking, judging

Pre-registration §5 (rev 3.4) set up two OpenRouter judges: a paid model scoring the stratified
sample of 600, and a free model from another family scoring 100 of those, with judge results
reported only if the two agreed. On 15 Nov 2026, before any main-data judging, the author
changed this (`DEVIATIONS.md`): one judge, `glm-5.2` on Adaption (sponsor credits), and no
cross-check. Its scores are exploratory and unvalidated, and confirmatory H3 is not tested
(section 10). No human labels are used.

**9a. Choosing the judge (done 15 Nov 2026).**
1. Add `ADAPTION_API_KEY=...` to `.env` (section 2). `pip install -r requirements.txt` installs
   the `adaption` SDK.
2. List the models the key can call:
   ```
   python -c "import sys; sys.path.insert(0, '.'); from src import runner as R; R.load_env(R.REPO / '.env'); import adaption; print([m.id for m in adaption.Adaption().models.list().data])"
   ```
   The §5 exclusions apply: not from OpenAI (including gpt-oss), Qwen/Alibaba or Google, and not
   a router, an unnamed model or an Adaption `stack:`. On 15 Nov that left glm-5.2, glm-5.3-flash
   and deepseek-v4-flash, and the author chose glm-5.2.
3. Fill in `models.yaml` under `judges: main`:
   - `provider: adaption`, `model_id`, and `family` (the developer);
   - `temperature: 0.0`;
   - the prices, `price_credits_per_mtok` from Adaption's models page, and a `budget_credits` hard
     stop.

   Adaption has no JSON mode, seed or reasoning parameter. The prompt asks for JSON, the parser
   validates every reply, and reasoning stays at the provider default, which is logged as such.
   `grade.py` and the pilot check the criteria that can be checked mechanically, and refuse a
   configuration that breaks them. Commit it on its own (`e578ba5`):
   ```
   git add models.yaml
   git commit -m "Main judge chosen (pre-registration §5): glm-5.2 via Adaption"
   ```
4. Run the pilot judge check (section 4, stage 2). Done 15 Nov: 10 of 10 valid (`e64307a`).

**9b. The judge**, once every model has finished (section 8):
```
python src/grade.py --judge
```
```
3600 completed cells -> data\graded\responses.csv
  ...
main judge glm-5.2 via adaption: sample 600; already judged 0; to judge 600. Ctrl+C stops cleanly.
  [main judge] 25/600 judged (this run 25, valid 25) | 0.1210 credits spent
  ...
main judge: 600 judged in this run (598 valid); 600 of 600 in all; 2.9000 credits spent on this model.
Every response in the main judge's sample is judged.
No cross-check judge: it was dropped (15 Nov 2026, by the author's decision; see DEVIATIONS.md). The §5 gate cannot be evaluated, so confirmatory H3 is not tested (Holm p = 1) and the main judge's scope-accuracy scores are reported as exploratory and unvalidated.
```
- **The sample.** The first run draws the 600 across all four models and fixes them in
  `data/graded/judge_sample.csv`. While any model still has cells to run, `grade.py` refuses to
  draw it and lists them.
- **How it runs.** 8 requests run at once, so this takes minutes, not hours. Each response is
  judged once; a re-run skips what this model has already judged.
- **Logs.** Every attempt, failed or not, goes to `data/graded/judge_main.attempts.jsonl`; the
  judgements go to `judge_main.jsonl`. The SDK's own retries are off, so every attempt is one the
  judge makes and logs.
- **Cost.** `budget_credits` in `models.yaml` (10 credits) is a hard stop on the cost computed from
  the prices in `models.yaml`. Adaption also reports each call's cost in its usage, which is logged
  with every call; the two agreed on every pilot call.

**9c. The cross-check judge: dropped** (`DEVIATIONS.md`, 15 Nov 2026). `python src/grade.py
--crosscheck` refuses:
```
The cross-check judge cannot run:
  - the cross-check judge was dropped (15 Nov 2026, by the author's decision; see DEVIATIONS.md): no cross-check is run, and the §5 kappa gate cannot be evaluated.
```

The judge prints every failed attempt as `[main judge] HTTP ...`, and Ctrl+C stops it cleanly.

## 10. The §5 agreement gate: cannot be evaluated

The pre-registered gate reports judge results only if the two judges' linear-weighted kappa on
the 100 cross-checked responses is at least 0.6. With the cross-check dropped there is no kappa:
```
python src/grade.py --agreement
```
```
No cross-check judge: it was dropped (15 Nov 2026, by the author's decision; see DEVIATIONS.md). The §5 gate cannot be evaluated, so confirmatory H3 is not tested (Holm p = 1) and the main judge's scope-accuracy scores are reported as exploratory and unvalidated.
```
`data/graded/judge_agreement.json` records the status `unevaluable`. The consequences, in
`src/analyse.py` and in the report:
- Confirmatory H3 is not tested. It enters the Holm family with p = 1, so the family stays at
  eight.
- The scope-accuracy numbers are reported as exploratory and unvalidated, and labelled so
  wherever they appear: the 0/1/2 distribution, the mention share, Figure 3 and the examples.
- So is H3's statistic computed from the one judge's scores (`h3_exploratory.csv`). It is outside
  the Holm family, so its p is unadjusted.

The agreement code still runs on the synthetic rehearsal, which fakes a cross-check (section 3).
There it prints PASSED, FAILED or PENDING, as pre-registered.

Commit the grades:
```
git add data/graded
git commit -m "Grading: the judge's scores (exploratory, unvalidated)"
```

## 11. Analysis

```
python src/analyse.py
```
```
results -> data\results
  scope-accuracy source: exploratory (no cross-check judge (dropped: DEVIATIONS.md, 15 Nov 2026), so the §5 gate cannot be evaluated: the main judge's scores are exploratory and unvalidated, and confirmatory H3 is not tested); 28 draft slots filled automatically, 0 need a hand fill
  EXPLORATORY: every scope-accuracy number is exploratory and unvalidated (one judge, no cross-check); confirmatory H3 is not tested; h3_exploratory.csv holds H3's statistic outside the Holm family
```
- The source reads one of four values:
  - `exploratory`: the run as it stands since 15 Nov 2026. There is no cross-check judge
    (`DEVIATIONS.md`), so the §5 gate cannot be evaluated.
    - Confirmatory H3 is not tested and enters Holm with p = 1.
    - The judge's scores, and H3's statistic computed from them (`h3_exploratory.csv`, outside the
      Holm family), are reported as exploratory and unvalidated.
    - The summary, CSVs, Figure 3, the examples and the draft slots all carry that label. Keep it
      wherever a scope-accuracy number is cited.
  - `judge`: the §5 gate passed (only with a cross-check).
  - `withheld`: the cross-check is unfinished, or the kappa is below 0.6. The H3 text then says
    why scope accuracy is not reported, and H3 enters Holm with p = 1.
  - `none`: no judge scores exist yet.
- `--scope-source judge` forces the judge's scores in whatever the gate says, for a look only.
  The summary is then stamped `JUDGE RESULTS FORCED`, and those numbers may not be reported.
- Any `by hand:` line names a draft slot the script could not fill. Fill it from the tables.
- A `PROTOCOL CHECK FAILED` line means a model logged more than one reasoning setting. Record it
  in `DEVIATIONS.md`.

Outputs in `data/results/`:

| File | Use |
|---|---|
| `results_summary.md` | Baseline (C0) and C0-ceiling section, ready-to-paste text for every slot, test tables, per-model table, robustness check |
| `REPORT_DRAFT.filled.md` | The draft with every slot substituted, for checking |
| `fig1_acceptance.png` | Figure 1, §4.2 |
| `fig2_discrimination.png` | Figure 2, §4.4 |
| `fig3_scope_accuracy.png`, `fig4_interpreter.png` | Optional figures for §4.5 and §4.7; Figure 3 is exploratory and unvalidated |
| `example_justifications.md` | Candidate verbatim quotes for §4.5, with exploratory, unvalidated scores |
| `scope_distribution.csv` | H3: mention share and the 0/1/2 shares with 95% CIs (exploratory, unvalidated) |
| `h3_exploratory.csv` | H3's statistic on the one judge's scores, per scope and claim type, outside the Holm family |
| `parse_failures_by_condition.csv`, `parse_failure_types.csv` | Parse failures per model and condition, flagged where a rate is over double the model's own, and what the failed generations looked like. The summary's "Parse failures" section says whether they concentrate in a condition. |
| `robustness_without_qwen.csv`, `robustness_qwen_bounds.csv` | Exploratory checks (`DEVIATIONS.md`, 15 Nov): every primary test pooled without qwen3.8-27b, and qwen3.8-27b's tests with its parse failures set to accept = false, then true |
| `primary_tests.csv` and the other CSVs | Every number, per model and claim type |

How to read the numbers:
- **Headline numbers** are the real-obscure pairs for H1–H3 and H2b (pre-registration rev 3),
  all pairs for H4, and invented minus real-obscure for H5, which is exploratory and unadjusted.
- **Tests** are paired t-tests over twin pairs, with Holm correction over the eight primary
  tests.
- **H3** is supported only if the upper bound of the 95% CI for the share of
  credential-mentioning justifications scored 2 is below 50% and its p_holm is below .05.
  Without the cross-check (section 10), H3 is not tested.
  - The summary's "Scope accuracy (H3): exploratory, unvalidated" section says so.
  - It gives the full 0/1/2 distribution and the share mentioning the credential, all with CIs.
  - It also reads H3's statistic against the rule, outside the Holm family. Cite all of these
    only as exploratory and unvalidated.
- **Robustness section.** If it lists a disagreement between the t-test and the permutation
  test, report the t-test, which is the pre-specified primary, and give the permutation result
  beside it.
- **Exploratory robustness checks.** They were added after the parse-failure pattern was seen,
  so they are exploratory. Cite them only as such, never as pre-registered tests.
  - The summary lists which conclusions change without qwen3.8-27b, and which change within its
    parse-failure bounds.
  - It lists separately the tests that cannot be run because every pair is at the C0 ceiling.
- **H4 and parse failures.** The "Interpreter arm (H4)" section, and the §4.7 slot, state any
  model whose interpreter arm failed to parse more often than the same conditions without it.
  qwen3.8-27b's does, at 15.8% against 7.9%; keep that caveat beside its H4 result.
- **Small samples.** With 10 real-obscure pairs, a modest effect can miss significance. Say so
  using the CI rather than calling it "no effect". The generated sentences already do this.
- **Not testable.** A test with fewer than 3 pairs, or with the same difference in every pair,
  is reported as "not testable". It shows its mean and pair count, with no p-value or CI, and
  enters Holm with p = 1. This is a post-data correction (`DEVIATIONS.md`, 15 Nov). The C0-ceiling
  rule can leave an inflation test (H1, H2) with too few pairs.
  - The summary's "Baseline (C0) and the C0-ceiling rule" section lists such tests and gives the
    full-sample result beside each.
  - Report the test as not testable, and use the full-sample result as the informative one, with
    its p labelled unadjusted.
  - If credentials lowered acceptance, the text says H1 is not supported and the effect runs the
    opposite way. Keep that wording.

The tests and decision rules are those of `PREREGISTRATION.md` §7: rev 3.3, fixed before any
data, plus the judge gate of rev 3.4, fixed after the pilot's first run and before the main run.

Commit the results:
```
git add data/results
git commit -m "Analysis results"
```

## 12. Failure modes and fixes

**Setup**

| You see | Meaning | Do this |
|---|---|---|
| `ModuleNotFoundError: No module named 'pandas'` (or scipy, matplotlib) | Libraries missing | `pip install -r requirements.txt` |
| Tests report `failed` | The environment or files differ from the frozen state | `git status`; restore changed files with `git checkout -- <file>`; re-run the tests. Do not start the run with failing tests. |
| `groq: GROQ_API_KEY not set` or `[model] GEMINI_API_KEY is not set; skipping this model.` | `.env` missing, misnamed, or key empty | Copy `.env.example` to `.env` and fill both keys. The file must be named exactly `.env`. |
| `--check-models` shows `NOT LISTED` | The provider withdrew or renamed the model. `qwen/qwen3.8-27b` is a preview model. | Do not substitute another model silently. Record it in `DEVIATIONS.md`, then run the rest: `python src/runner.py --models gpt-oss-120b,gpt-oss-20b,gemini-3.5-flash-lite` |

**Main run**

| You see | Meaning | Do this |
|---|---|---|
| State `waiting 23s (per-minute limit)` | A 429 per-minute limit | Nothing; it waits and continues. If it never stops waiting, lower that model's `rpm`/`tpm` in `models.yaml` (pacing only) and re-run. |
| `daily limit reached (...). Stopping this model; resume after ... local.` | The day's quota is used (Gemini: 500) | Re-run `python src/runner.py` after the printed local time |
| Gemini stops well before 500 | Google's real quota is lower than configured | Same: re-run after the printed time. If Gemini cannot finish in time, see the cut order (section 15). |
| `HTTP 400 blocked_api_access ... Stopping ALL groq models` | Groq blocked the account (billing, spend limit, account status) | Fix it at console.groq.com, then re-run the same command |
| State `skipping a cell after repeated transient errors` | 5xx, 498 or network failures, retried 5 times | Nothing now; the cell stays undone. Re-run later to pick it up. |
| `[model] HTTP 401 ...; stopping this model` | Wrong or revoked key | Fix `.env`, re-run |
| `[model] HTTP 404 ...` or another 4xx; stopping this model | Model id or request rejected | `python src/runner.py --check-models`. Read the last lines of `data/logs/<model>.events.jsonl` (section 15). |
| `BUDGET HARD STOP: $4.4xxx spent of the $4.50 cap` | The next call could pass $4.50 | Do not raise the cap without a decision. Either stop with what you have, or apply the cut order and record it in `DEVIATIONS.md`. Completed cells are kept. |
| `WARNING: the projection ($X) is above the hard stop` before starting | The measured cost projects above $4.50 | Answer `n`. Apply the cut order first. |
| State `CRASHED: ... (see events log)` | An unexpected error in that model's worker; the others continue | Read the traceback in `data/logs/<model>.events.jsonl` (event `crash`), then re-run. If it crashes on the same cell every time, record it in `DEVIATIONS.md` and run the other models with `--models`. |
| Laptop slept, Wi-Fi dropped, or the terminal closed | Calls failed or the process died | Re-run `python src/runner.py`. Nothing is lost except calls in flight. |
| Events log shows `json_validate_failed` (Qwen) | Groq's schema check rejected the model's answer (HTTP 400) | Nothing; this is handled. The generated text is parsed like any reply, retried once with the next seed, then recorded as `parse_failed` if it still fails. The raw line keeps the generated text. |
| Many `parse_failed` for one model | The model returns invalid JSON | Do not change settings mid-run, and do not re-run the failed cells: they are missing data. `python src/parse_failures.py --model <model>` breaks them down by condition, interpreter, claim type and truth, and by failure type (read-only). Report the rate per model and whether failures concentrate in a condition (`results_summary.md`, "Parse failures"). |
| `No model has an API key; nothing to do.` | `.env` not found | Run from the repository folder; check `.env` |

**The judges**

| You see | Meaning | Do this |
|---|---|---|
| `The pilot's judge check needs the main judge, which cannot run yet` | No judge chosen yet | `python src/runner.py --pilot --skip-judge` for the study calls; the judge check after section 9a |
| `The main judge cannot run:` or `The cross-check judge cannot run:`, then a list | `models.yaml` breaks a §5 criterion, or a field is empty | Fix what the list names (section 9a), commit, re-run |
| `... failed the pilot judge check` | The chosen judge returned fewer than 9 of 10 valid scores | Correct the request or choose the next candidate (section 4, stage 2) |
| `Note: the pilot has no passed judge check for ...` | The check has not been run for this model | Run `python src/runner.py --pilot` first |
| `The judge sample is drawn once, across every model, so it waits for the main run to finish` | A model still has cells to run | Finish the main run. `--force` draws the sample anyway; record that in `DEVIATIONS.md`. |
| `ADAPTION_API_KEY is not set` | Key missing from `.env` | Add the line `ADAPTION_API_KEY=...` to `.env` |
| `[main judge] HTTP 503: ...; retry 2 of 5 in 20s`, or `HTTP None: ReadTimeout`, or `HTTP 200: Provider returned error` | The provider is busy, the call timed out, or an error came back inside a 200 | Nothing; it retries 5 times. Every attempt is logged in the `.attempts.jsonl` file. |
| `[main judge] HTTP 429: ...; rate limited: retrying in Ns` | Adaption is limiting the request rate (its limits are not documented) | Nothing; it waits (Retry-After, if sent) and retries, up to 10 times per response |
| `Adaption reports that today's limit ... is used up` | Adaption reported a daily limit | Re-run later; the judge resumes where it stopped |
| `Stopped: Adaption reports insufficient credits (HTTP 402)` | The organisation's credits are used up | Check the credit balance with Adaption, re-run |
| `Stopped: spend cap passed: ...` | `budget_credits` for the judge was passed | Check the spend; raise the cap only by decision |
| `The cross-check judge cannot run: ... was dropped` | The cross-check is dropped (`DEVIATIONS.md`) | Nothing: it is not part of the run (section 9c) |
| `Stopped: ... kept failing` or `... stayed rate-limited` | Provider trouble | Wait 10–30 minutes, re-run |
| `Stopped: the request was rejected (HTTP 4xx)` | Key, model id or a parameter Adaption does not accept | Check the key and `model_id` against the model list (section 9a); read the `body` in the `.attempts.jsonl` file |
| `Interrupted in the judge stage: ...` (pilot) or `Interrupted: finishing the judge calls in flight` | You pressed Ctrl+C | Re-run the same command. Judged responses are kept; an interrupted pilot check reports INCOMPLETE, not FAIL. |

**Analysis**

| You see | Meaning | Do this |
|---|---|---|
| `No responses in data\raw` | Wrong folder or no data | Run from the repository folder |
| `scope-accuracy source: none` | No main-judge scores yet | Finish section 9, re-run |
| `scope-accuracy source: exploratory` | No cross-check judge (dropped, `DEVIATIONS.md`): the expected source for this run | Report scope accuracy as exploratory and unvalidated, and H3 as not tested (section 13) |
| `scope-accuracy source: withheld` | Only with a cross-check: it is unfinished, or the judges' kappa is below 0.6 | Not expected in this run (the cross-check is dropped) |
| `by hand: {...}` | A draft placeholder the script does not recognise (the draft was edited) | Fill it from the tables in `results_summary.md` |
| `PROTOCOL CHECK FAILED` | A model logged two reasoning settings | `DEVIATIONS.md` entry; report it |
| A slot says `not available` | That part of the data is missing (for example, the interpreter arm was cut) | Say so in the report |

**If something is not in this table:** stop, read the last lines of the events log, write down
what happened in `DEVIATIONS.md`, and re-run. Re-running is always safe.

## 13. Filling REPORT_DRAFT.md

1. **Start from the filled preview.** Copy `data/results/REPORT_DRAFT.filled.md` to `REPORT.md`
   in the repository root, and leave `REPORT_DRAFT.md` as it is. Delete the first line (the
   `AUTO-FILLED PREVIEW` comment) and the "Before submitting" instruction block near the top.
2. **Check every substituted sentence** against `results_summary.md`. The summary lists each
   slot with its line number, and every number comes from its tables. Rewrite the wording as
   you like, but keep the numbers. Where a sentence says "did not reliably change", keep that
   meaning: it reflects the test, not a style choice.
3. **Check the text no slot covers**, listed under "Other text in REPORT_DRAFT.md to check" in
   `results_summary.md`:
   - the `DEVIATIONS.md` reference;
   - the collection dates;
   - the pre-registration commit cited in §3 (the summary flags it if `PREREGISTRATION.md`
     changed after that commit);
   - the §3.4, §4.5 and Appendix A text on the judge: scope accuracy is exploratory and
     unvalidated (one judge, no cross-check: section 10), and H3 was not tested. Keep that label
     beside every scope-accuracy number, table, figure and example.

   The draft's facts were updated before the main run (rev 3.4, the four models, the tests, the
   H3 rule) and again on 15 Nov 2026 for the single judge (`DEVIATIONS.md`).
4. **Figures:** Figure 1 goes in §4.2 and Figure 2 in §4.4. Figures 3 and 4 are optional for
   §4.5 and §4.7, if space allows (8 pages maximum before references and appendices).
5. **§4.5 examples:** pick one correct and one misattributing justification from
   `example_justifications.md`. Read the whole response before quoting it. Their scores are
   exploratory and unvalidated; say so if you give them.
6. **§4.8 models:** use the "Per model" table and the "Scale within family" line from
   `results_summary.md`. Report each model's parse-failure rate (CLAUDE.md requires it).
7. **Discussion:** one paragraph per point in the draft's structure. Report the countermeasure
   result with equal prominence whichever way it went.
8. **Abstract last:** 150–250 words. To count, paste it into a word counter or run
   `python -c "print(len(open('abstract.txt',encoding='utf-8').read().split()))"` on a text file.
9. **References:** open every one marked `[verify]`, fix authors and titles, and delete the tag.
   Remove any reference you cannot verify.
10. **Pre-sprint vs sprint work.** The README and Appendix A must say three things:
    - the design, corpus, code, probes and pre-registration predate the sprint;
    - a pilot of the study calls ran on 10–11 Nov, before the sprint, and is excluded from
      analysis;
    - the main data were collected during the sprint (13–15 Nov), with the dates.

    `results_summary.md` gives the first and last collection times. The pilot's responses carry
    their own timestamps in `data/pilot/`.

## 14. Submission checklist

- [ ] `python src/runner.py --dry-run` shows `to run 0` for every model, or every gap is explained
      in `DEVIATIONS.md`.
- [ ] Nothing in `data/raw/` was edited: `git diff --stat data/raw` shows only additions since the
      last commit (or nothing).
- [ ] `DEVIATIONS.md` lists every change made after data collection began (only its header
      means none).
- [ ] The report contains no `{`: `Select-String -Path REPORT.md -Pattern '\{'` prints nothing.
- [ ] The report gives:
      - each model's parse-failure rate and reasoning setting;
      - the judge's model ID and provider (glm-5.2 via Adaption) and its settings;
      - that the cross-check was dropped, so the §5 gate could not be evaluated and H3 was not
        tested;
      - the label "exploratory and unvalidated" on every scope-accuracy number.
- [ ] The countermeasure result is reported, whichever way it went.
- [ ] The Limitations and Dual-Use appendix is present. It states that the failure mode needs no
      forgery, and why the work is published now.
- [ ] Abstract 150–250 words; main text no more than 8 pages; official template from the
      sprint's Guidelines tab.
- [ ] Every reference verified; no `[verify]` tags left.
- [ ] README: the "Pre-sprint vs sprint work" section matches what happened, with dates.
- [ ] The report says the main data were collected during the sprint, with the dates from
      `results_summary.md`, and that only the pilot (10–11 Nov) came before it.
- [ ] `.env` was never committed: `git log --all --oneline -- .env` prints nothing.
- [ ] Everything is committed and pushed:
      ```
      git add REPORT.md DEVIATIONS.md README.md data
      git commit -m "Results and report"
      git push
      git tag -a sprint-submission -m "As submitted"
      git push origin sprint-submission
      ```
- [ ] Submitted through the sprint's form, with the repository link.

## 15. Appendix: cut order, logs, status commands

**Cut order** (CLAUDE.md). Use it only if quota or budget forces it. Before running anything
with a cut, write the `DEVIATIONS.md` entry.

| Step | Cut | How |
|---|---|---|
| 1 | Countermeasure arm narrows to C1 only | `models.yaml`, under `defaults`: `interpreter_conditions: [C1]` |
| 2 | Drop `gemini-3.5-flash-lite` | Run with `--models gpt-oss-120b,gpt-oss-20b,qwen3.8-27b` |
| 3 | Reps 3 → 2 | `models.yaml`, under `defaults`: `reps: 2` |
| never | Real-obscure half, or C0 | — |

Check the effect with `python src/runner.py --dry-run` before starting. Cells already completed
are kept and still analysed.

**Status without making calls:** `python src/runner.py --dry-run` shows done and to-run per model,
spend so far, and the projection.

**Logs** in `data/logs/`:
- `<model>.events.jsonl` records rate limits (`http_429`, `daily_limit`), retries
  (`transient_error`), stops (`budget_stop`, `blocked_api_access`, `fatal_http_error`) and
  crashes (`crash`, with a traceback).
- `runs.jsonl` has one line per run.
- `<model>.order.<plan>.json` holds the randomised cell order.

To see the last events:
```
Get-Content data\logs\qwen3.8-27b.events.jsonl -Tail 5
```

**Judge logs** in `data/graded/`. Each line in `judge_main.attempts.jsonl` records one HTTP
attempt, failed or not:
- status, outcome, latency and cost (`cost_credits` on Adaption);
- the provider that served it and the model it reported;
- the full body of a failure.

The judgements are in `judge_main.jsonl`; with the cross-check dropped there is no
`judge_crosscheck.jsonl`. The pilot's judge check uses `data/pilot/judge_check.jsonl` and
`data/pilot/logs/judge_check.attempts.jsonl`, and the one test call before it
`data/pilot/judge_test_call.jsonl`, which nothing reads. Rows by
any judge model other than the one in `models.yaml` are ignored. This includes
`data/pilot/judge.jsonl`, from the judge replaced in rev 3.4.

**Raw responses** are in `data/raw/<model>.jsonl`, one line per API call:
- what was sent: the request body, seed, temperature and reasoning setting;
- what came back: the response, `raw_text`, the parsed answer and `status`;
- tokens and cost.

A `parse_retry` line is superseded by the cell's next attempt.

**Where things are**

| Path | Contents |
|---|---|
| `PREREGISTRATION.md` | The plan (rev 3.4), including the tests and decision rules (§7) and the judges (§5) |
| `DEVIATIONS.md` | Changes made after data collection began |
| `REPORT_DRAFT.md` | The draft with `{PLACEHOLDER}` slots |
| `models.yaml` | Models, limits, prices, budget, the judge (the cross-check marked dropped) |
| `src/runner.py` | Study calls, pilot, dry run |
| `src/grade.py` | Metrics, the judge, and the agreement code and §5 gate (unevaluable without a cross-check) |
| `src/judge.py`, `src/providers/adaption.py`, `src/providers/openrouter.py` | The judge prompt, the §5 criteria check, concurrent resumable judging via Adaption (OpenRouter as planned) |
| `src/analyse.py` | Tests, figures, results summary |
| `src/synthetic.py` | Fake data for rehearsal and tests |
| `data/raw`, `data/pilot` | Append-only responses |
| `data/graded`, `data/results` | Derived; `data/graded` also holds the judge's paid calls, so keep it |
