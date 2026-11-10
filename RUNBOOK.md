# Runbook: running the sprint without AI help

Everything from the pilot to submission, in order. Run every command from the repository folder
in a terminal (VS Code: *Terminal → New Terminal*). Times are IST. Each step says what you should
see; section 12 lists what can go wrong and what to do.

## Contents

1. [Rules that hold throughout](#1-rules-that-hold-throughout)
2. [Setup check](#2-setup-check-once-before-the-pilot)
3. [Rehearsal on synthetic data](#3-rehearsal-on-synthetic-data-no-api-calls)
4. [The pilot](#4-the-pilot-first)
5. [Freeze](#5-freeze-right-after-the-pilot)
6. [Timeline](#6-timeline)
7. [Main run: Groq, then Gemini](#7-main-run-groq-then-gemini)
8. [Gemini, second quota day](#8-gemini-second-quota-day)
9. [Grading and the judge](#9-grading-and-the-judge)
10. [Hand-labels and kappa](#10-hand-labels-and-kappa)
11. [Analysis](#11-analysis)
12. [Failure modes and fixes](#12-failure-modes-and-fixes)
13. [Filling REPORT_DRAFT.md](#13-filling-report_draftmd)
14. [Submission checklist](#14-submission-checklist)
15. [Appendix: cut order, logs, status commands](#15-appendix-cut-order-logs-status-commands)

---

## 1. Rules that hold throughout

- **Data collection starts before the sprint** (13–15 Nov 2026), so it must be disclosed. The
  README says so, and the report must give the collection dates (section 13). The pilot (30
  calls, section 4) is excluded from analysis.
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
You should see a final line like `447 passed in 90s`: no `failed` and no `error`.

Check that both keys are present, without printing them:
```
python -c "import pathlib; print(sorted(l.split('=')[0] for l in pathlib.Path('.env').read_text().splitlines() if '=' in l and l.split('=',1)[1].strip()))"
git check-ignore .env
```
You should see `['GEMINI_API_KEY', 'GROQ_API_KEY']`, then `.env` (git ignores it).

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
The judge model is not listed here; the pilot exercises it.

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
  scope-accuracy source: judge; 27 draft slots filled automatically, 0 need a hand fill
```
Open `data/synthetic/results/results_summary.md`, `REPORT_DRAFT.filled.md` and the four PNGs.
The fake data raises acceptance in C1–C4, separates the twins in C5, and has the interpreter
cut acceptance. `data/synthetic/` is git-ignored; delete it whenever you like.

## 4. The pilot (first)

```
python src/runner.py --pilot
```
This makes 20 study calls, then 10 judge calls:
- Each model answers claim `real-01-t` in C0, C1, C2 and C5.
- Each also answers one extra cell: C2 with the interpreter for the three Groq models, C4 for
  Gemini.
- The judge then scores 10 of those answers.

Everything goes to `data/pilot/`, which the analysis never reads. Cost is about $0.02; time is a
few minutes. It starts with
`PILOT: 20 study calls on real-01-t, then up to 10 judge calls. Output: data\pilot`, prints
progress, prints the report, and ends with
`Saved data\pilot\pilot_report.md and pilot_report.json.`

Read `data/pilot/pilot_report.md` and act on it:

| The report shows | Meaning | Do this |
|---|---|---|
| Every study row `ok` | Models return valid JSON | Nothing |
| A row `PARSE FAIL` | That call's JSON failed twice | Open `data/pilot/<model>.jsonl` and read `raw_text` and `finish_reason`. If `finish_reason` is `length`, the answer was cut off: raise that model's `max_output_tokens` in `models.yaml` before the freeze. One failure is not a blocker; parse failures are reported per model. |
| Judge `**PASS**` (at least 9 of 10 valid) | The judge will score scope accuracy | Section 9, judge path |
| Judge `**FAIL**` | Pre-registered fallback: your hand-labels | Section 9, fallback path |
| `WARNING: projected total ... above $4.00` | The full run may hit the $4.50 hard stop | Apply the cut order (section 15) before the main run and record it in `DEVIATIONS.md` |
| `Projected total including spend so far: $X` | Cost of the full run, from measured tokens | Keep this number for the report |

Then commit the pilot. It is disclosed data:
```
git add data/pilot
git commit -m "Pilot: 20 study calls and 10 judge calls on real-01-t (disclosed; excluded from analysis)"
```

## 5. Freeze (right after the pilot)

```
git status
git tag -a sprint-freeze -m "Code, corpus and analysis frozen before the main run"
```
`git status` should report nothing to commit. From here, no code changes. If a bug forces one,
commit it on its own with a message saying why, and add a `DEVIATIONS.md` entry.

## 6. Timeline

Data collection starts now, in this order: the pilot, the freeze, the three Groq models, then
gemini-3.5-flash-lite.

| Step | What | Command | Takes |
|---|---|---|---|
| 1 | Pilot, then read its report | `python src/runner.py --pilot` | a few minutes |
| 2 | Freeze | section 5 | 2 min |
| 3 | Groq: gpt-oss-120b, gpt-oss-20b, qwen3.8-27b | `python src/runner.py --models gpt-oss-120b,gpt-oss-20b,qwen3.8-27b` | 30–90 min |
| 4 | Gemini, up to its daily quota | `python src/runner.py --models gemini-3.5-flash-lite` | ~40 min, then it stops for the day |
| 5 | Gemini's remaining cells, after the time it prints | the same command | ~20 min |
| 6 | Grade and judge, once all four models are done | `python src/grade.py --judge` | ~45 min |
| 7 | Hand-label 30 (or 150 on the fallback path) | section 10 | 45 min (150: 3–4 h) |
| 8 | Analysis | `python src/analyse.py` | 1 min |
| 9 | Write up, check, submit | sections 13–14 | |

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
- Do **not** run `--judge` yet. The judge sample is drawn once, stratified across all four
  models, so it must wait for Gemini to finish.

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

## 9. Grading and the judge

**Judge path (the pilot report said PASS).**
```
python src/grade.py --judge
```
```
3600 completed cells -> data\graded\responses.csv
  ...
judge sample 600; already judged 0; to judge 600
  judged 25/600
  ...
  judged 600/600
```
This takes about 45 minutes, paced to stay under the judge's limits. If it stops early, re-run
the same command; judged items are kept and the sample is fixed once drawn. Then go to section
10a.

**Fallback path (the pilot report said FAIL).** `grade.py --judge` refuses and prints the §5
rule. Per pre-registration §5, scope accuracy comes from your hand-labels on 150 responses.
Weighted kappa must still be reported, so collect judge scores as secondary data first:
```
python src/grade.py --judge --force
```
Then go to section 10b. If the judge cannot run at all, skip `--force`, label 150, and record
in `DEVIATIONS.md` that kappa could not be computed.

## 10. Hand-labels and kappa

**10a. Judge path: label 30.**
```
python src/grade.py --human-sample 30
```
```
30 items from judged responses (for agreement) -> data\human\human_sample_30.csv
key (do not open while labelling) -> data\human\human_key_30.csv
instructions -> data\human\HOW_TO_LABEL.md
```
1. Read `data/human/HOW_TO_LABEL.md`.
2. Open `human_sample_30.csv` in Excel, LibreOffice or Google Sheets. For each row, read
   `credential_facts`, `statement` and `explanation`, then type `2`, `1`, `0` or `NA` in the
   `score` column. Do not add, delete or reorder rows, and **do not open the `human_key`
   file** until you have finished: it reveals model, condition and truth.
3. Save as CSV with the same name. In Excel: *File → Save As → CSV UTF-8 (Comma delimited)*.
4. Import:
   ```
   python src/grade.py --import-human data/human/human_sample_30.csv
   ```
   ```
   30 labels imported -> data\graded\human_labels_30.csv
   judge-human agreement on 30 items: weighted kappa (linear, items both scored 0-2) 0.71 (n=24); exact 0.77; NA agreement 0.93
     gemini   n=  8  weighted kappa ...
   ```

**10b. Fallback path: label 150.** Run the same steps with 150:
```
python src/grade.py --human-sample 150
python src/grade.py --import-human data/human/human_sample_150.csv
```
These labels become the scope-accuracy measure. Kappa comes from the items the forced judge
also scored. Labelling 150 takes 3–4 hours, so split it into sittings and save often.

Commit the labels and grades:
```
git add data/graded data/human
git commit -m "Grading, judge scores and hand-labels"
```

## 11. Analysis

```
python src/analyse.py
```
```
results -> data\results
  scope-accuracy source: judge; 27 draft slots filled automatically, 0 need a hand fill
```
- The source reads `human` on the fallback path. It reads `none` if no scope scores exist yet;
  the H3 text then says scope scores were not available.
- Any `by hand:` line names a draft slot the script could not fill. Fill it from the tables.
- A `PROTOCOL CHECK FAILED` line means a model logged more than one reasoning setting. Record it
  in `DEVIATIONS.md`.

Outputs in `data/results/`:

| File | Use |
|---|---|
| `results_summary.md` | Ready-to-paste text for every slot, test tables, per-model table, robustness check |
| `REPORT_DRAFT.filled.md` | The draft with every slot substituted, for checking |
| `fig1_acceptance.png` | Figure 1, §4.2 |
| `fig2_discrimination.png` | Figure 2, §4.4 |
| `fig3_scope_accuracy.png`, `fig4_interpreter.png` | Optional figures for §4.5 and §4.7 |
| `example_justifications.md` | Candidate verbatim quotes for §4.5 |
| `scope_distribution.csv` | H3: mention share and the 0/1/2 shares with 95% CIs |
| `primary_tests.csv` and the other CSVs | Every number, per model and claim type |

How to read the numbers:
- **Headline numbers** are the real-obscure pairs for H1–H3 and H2b (pre-registration rev 3),
  all pairs for H4, and invented minus real-obscure for H5, which is exploratory and unadjusted.
- **Tests** are paired t-tests over twin pairs, with Holm correction over the eight primary
  tests.
- **H3** is supported only if the upper bound of the 95% CI for the share of
  credential-mentioning justifications scored 2 is below 50% and its p_holm is below .05.
  The summary's "Scope accuracy (H3)" section states the verdict and gives the full 0/1/2
  distribution and the share mentioning the credential, all with CIs.
- **Robustness section.** If it lists a disagreement between the t-test and the permutation
  test, report the t-test, which is the pre-specified primary, and give the permutation result
  beside it.
- **Small samples.** With 10 real-obscure pairs, a modest effect can miss significance. Say so
  using the CI rather than calling it "no effect". The generated sentences already do this.

The tests and decision rules are those of `PREREGISTRATION.md` §7 (rev 3.3), fixed before any
data.

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
| Many `parse_failed` for one model | The model returns invalid JSON | Do not change settings mid-run. Look at `raw_text` and `finish_reason` in `data/raw/<model>.jsonl`. Report the rate per model (it is in `per_model.csv`). |
| `No model has an API key; nothing to do.` | `.env` not found | Run from the repository folder; check `.env` |

**Grading and the judge**

| You see | Meaning | Do this |
|---|---|---|
| `The judge FAILED the pilot ...` | The pre-registered pass rule failed | Fallback path (sections 9–10b) |
| `Note: no pilot report found` | `data/pilot/pilot_report.json` is missing | Run the pilot first, or note it in `DEVIATIONS.md` |
| `Judge RPD 1000 reached; resume after ...` | The configured daily cap | Re-run after the printed time |
| `Judge stopped: judge daily quota exhausted` | Google's daily quota for Gemma | Re-run after 13:30 IST; judged items are kept |
| `Judge stopped: judge failing repeatedly: HTTP 5xx` | Provider trouble | Wait 10–30 minutes, re-run |
| `Judge stopped: judge request rejected: HTTP 4xx` | Key or model id problem | Check `GEMINI_API_KEY`; the judge model is `gemma-4-31b-it` in `models.yaml` |
| `human_sample_30.csv already exists (it may hold your labels)` | Protects your labels | Keep the file. Only use `--overwrite` to start labelling again. |
| `N items have no valid score (need 2, 1, 0 or NA): [...]` | Empty or mistyped cells | Fill those items and import again |
| `KeyError` during `--import-human` | Rows were added or renumbered | Restore the `item` column. The labels file must match its `human_key` file. |
| All columns land in one column in Excel | Locale delimiter | Open with LibreOffice or Google Sheets, or use Excel's *Data → From Text/CSV* with comma |

**Analysis**

| You see | Meaning | Do this |
|---|---|---|
| `No responses in data\raw` | Wrong folder or no data | Run from the repository folder |
| `scope-accuracy source: none` | No judge scores and no 150 hand-labels | Finish section 9 or 10, re-run |
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
3. **Fix the stale text** listed under "Other text in REPORT_DRAFT.md to update" in
   `results_summary.md`:
   - pre-registration rev 3.2 and its commit;
   - the old model sentence in §3.3;
   - "3.1 vs 3.5 Flash-Lite. Spot check." in §4.8;
   - the "spot check" wording in Appendix A;
   - the `DEVIATIONS.md` reference.
4. **Figures:** Figure 1 goes in §4.2 and Figure 2 in §4.4. Figures 3 and 4 are optional for
   §4.5 and §4.7, if space allows (8 pages maximum before references and appendices).
5. **§4.5 examples:** pick one correct and one misattributing justification from
   `example_justifications.md`. Read the whole response before quoting it.
6. **§4.8 models:** use the "Per model" table and the "Scale within family" line from
   `results_summary.md`. Report each model's parse-failure rate (CLAUDE.md requires it).
7. **Discussion:** one paragraph per point in the draft's structure. Report the countermeasure
   result with equal prominence whichever way it went.
8. **Abstract last:** 150–250 words. To count, paste it into a word counter or run
   `python -c "print(len(open('abstract.txt',encoding='utf-8').read().split()))"` on a text file.
9. **References:** open every one marked `[verify]`, fix authors and titles, and delete the tag.
   Remove any reference you cannot verify.
10. **Pre-sprint work and data.** The README and Appendix A must say three things:
    - the code predates the sprint;
    - a 30-call pilot ran before it;
    - the data were collected before the sprint (13–15 Nov), with the dates.

    `results_summary.md` gives the first and last collection times, and the pilot's date is in
    `data/pilot/pilot_report.md`.

## 14. Submission checklist

- [ ] `python src/runner.py --dry-run` shows `to run 0` for every model, or every gap is explained
      in `DEVIATIONS.md`.
- [ ] Nothing in `data/raw/` was edited: `git diff --stat data/raw` shows only additions since the
      last commit (or nothing).
- [ ] `DEVIATIONS.md` lists every change made after data collection began (only its header
      means none).
- [ ] The report contains no `{`: `Select-String -Path REPORT.md -Pattern '\{'` prints nothing.
- [ ] Each model's parse-failure rate, reasoning setting, judge pilot result and kappa (overall
      and per family) are in the report.
- [ ] The countermeasure result is reported, whichever way it went.
- [ ] The Limitations and Dual-Use appendix is present. It states that the failure mode needs no
      forgery, and why the work is published now.
- [ ] Abstract 150–250 words; main text no more than 8 pages; official template from the
      sprint's Guidelines tab.
- [ ] Every reference verified; no `[verify]` tags left.
- [ ] README: pre-sprint code, the pilot and the pre-sprint data collection disclosed, with dates.
- [ ] The report says the data were collected before the sprint, with the dates from
      `results_summary.md`.
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

**Raw responses** are in `data/raw/<model>.jsonl`, one line per API call:
- what was sent: the request body, seed, temperature and reasoning setting;
- what came back: the response, `raw_text`, the parsed answer and `status`;
- tokens and cost.

A `parse_retry` line is superseded by the cell's next attempt.

**Where things are**

| Path | Contents |
|---|---|
| `PREREGISTRATION.md` | The plan (rev 3.3), including the tests and decision rules (§7) |
| `DEVIATIONS.md` | Changes made after data collection began |
| `REPORT_DRAFT.md` | The draft with `{PLACEHOLDER}` slots |
| `models.yaml` | Models, limits, prices, budget, judge |
| `src/runner.py` | Study calls, pilot, dry run |
| `src/grade.py` | Metrics, judge, hand-labels, kappa |
| `src/analyse.py` | Tests, figures, results summary |
| `src/synthetic.py` | Fake data for rehearsal and tests |
| `data/raw`, `data/pilot` | Append-only responses |
| `data/graded`, `data/human`, `data/results` | Derived; safe to regenerate |
