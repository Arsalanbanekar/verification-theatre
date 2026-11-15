# Status

Last updated 16 Nov 2026, 01:30 IST. The sprint (13–15 Nov 2026) closes on 16 Nov at 11:59 UTC.

**Where things stand.** Data collection, judging and analysis are complete and committed.
- The report draft is merged and filled (`REPORT_DRAFT.md`, 16 Nov). Its title, abstract,
  Contributions, Results, Discussion and Appendix A are from the v2 sections, and §3 matches what
  was done.
- Every number in it was checked against `data/results/results_summary.md` and the results CSVs.
  Every reference marked for checking was confirmed and given its authors.
- The main text is an estimated 6.4–6.9 pages in a two-column template, within the 8-page limit.
- What remains: paste it into the official template and work through the submission checklist
  (RUNBOOK §14).

**Before the sprint**, tagged `pre-sprint` (`fee706c`): the design, corpus, code, both probes, the
pre-registration (revs 1–3.4) and a pilot of the study calls on 10–11 Nov (`data/pilot/`, excluded
from analysis). README.md, "Pre-sprint vs sprint work", gives the dates and commits.

**During the sprint**, in this order:
1. **Main data collection: 3,600 of 3,600 cells** (`data/raw/`).
   - The three Groq models ran at `fee706c`, 19:34–19:45 UTC on 14 Nov.
   - gemini-3.5-flash-lite ran in three runs, from 19:51 UTC on 14 Nov to 10:33 UTC on 15 Nov.
   - Every logged request matches a rebuild from `fee706c` (README).
   - Parse failures: qwen3.8-27b 11.0%; the other three none.
2. **Judge: glm-5.2 via Adaption, one judge, no cross-check** (`DEVIATIONS.md`, 15 Nov).
   - The pilot judge check scored 10 of 10 valid (PASS).
   - In the main judging, 570 of 600 were valid at the 4,000-token cap. The 30 cut off at the cap were
     re-asked once at 12,000 tokens, and all 30 returned a score. That gives 600 of 600 valid.
   - Cost: 3.31 sponsor credits.
3. **Analysis** of all four models (`data/results/`, run at `36898c0`).
4. **Write-up**: next (RUNBOOK §13–14).

## Results at a glance

Real-obscure pairs, pooled over models; details and every table in `results_summary.md`.

- **Baseline ceiling.** gpt-oss-120b, gpt-oss-20b and gemini-3.5-flash-lite accepted every C0
  response, and qwen3.8-27b 90%. Pooled, 8 of 10 real-obscure pairs are at the C0 ceiling, so every
  pre-registered inflation test (H1, H2) is not testable. The full-sample result beside each is the
  informative one.
- **H1 is not supported, and the effect runs the opposite way.** In the full sample, the credential
  lowered acceptance by 15.0 points (95% CI 9.5 to 20.5; p < .001, unadjusted).
- **H2, full sample.**
  - C3 − C2: +3.1 (no reliable difference between an asserted and a gathered statement).
  - C4 − C1: −12.7 (p = .015, unadjusted).
  - C4 − C3: −21.7 (p < .001, unadjusted).
- **H2b.** Discrimination is flat over C1–C4 (−4.0 against C0, p = .053). It rises at C5, the positive
  control: +27.1 (p_holm = .022).
- **H3 is not tested**, because there is no cross-check judge (Holm p = 1).
  - Exploratory and unvalidated: 4% of credential-mentioning justifications scored 2 (95% CI 2–7%).
  - It is 0% in every pair for both gpt-oss models.
- **H4.** The interpreter lowered acceptance by 42.8 points (p_holm < .001).
  - Exploratory: it lowered true and false acceptance alike, from 85% to 44% and from 87% to 42%.
  - The discrimination index changed by +2.9 (95% CI −2.6 to +8.4), so there is no reliable gain in
    accuracy.
- **H5 (exploratory).** Credentials lowered acceptance of invented claims too (−5.4, p = .038,
  unadjusted), but less than of real ones (difference +9.6, p = .009). They did not rescue
  unrecognised sources.

## Deviations (`DEVIATIONS.md`)

1. 11 Nov: the judge was replaced after the pilot's first run (pre-registration rev 3.4).
2. 15 Nov, 01:51 IST: exploratory robustness checks for Qwen's parse failures.
3. 15 Nov, 16:04 IST: the degeneracy guard, a post-data correction. Not-testable tests get no p-value
   and enter Holm with p = 1; the full sample is reported beside every stratified result.
4. 15 Nov, 23:36 IST: the judge moved to Adaption (glm-5.2) and the cross-check was dropped. H3 is
   not tested, and scope accuracy is exploratory and unvalidated.
5. 16 Nov, 00:36 IST:
   - one re-ask of the 30 judgements cut off at the cap (30 of 30 valid);
   - the exploratory interpreter-discrimination analysis.

## Key decisions

- **Signer.** Vellumworth Document Services Ltd; the certificate issuer is Kestrelmoor Trust Services
  Ltd. Both are invented and screened, and identical everywhere. C4 changes only trust-list status.
- **Models (rev 3.2).**
  - gpt-oss-120b, gpt-oss-20b and qwen3.8-27b on Groq: the full design plus the interpreter arm.
  - gemini-3.5-flash-lite: the full design.
  - Temperature 0.7, and the lowest documented reasoning setting per model, logged per call.
- **Budget.**
  - Study calls: $2.56 spent of the $4.50 hard stop, pilot included.
  - The judge: 3.31 sponsor credits on Adaption.
- **Judge.** glm-5.2 via Adaption, blind to model, condition and truth.
  - Temperature 0; the provider's default reasoning (Adaption has no reasoning parameter).
  - JSON is asked for in the prompt and validated by the parser.
  - Output cap 4,000 tokens, and 12,000 for the one re-ask.
- **Analysis (§7).**
  - Paired t-tests over twin pairs, with Holm over the eight primary tests.
  - Sign-flip permutation tests as a robustness check.
  - The C0-ceiling rule, with the full sample reported beside each stratified result.
  - The degeneracy guard.

## Open issues for the write-up

1. **Framing (done 16 Nov).** The title and abstract now report what was found: credentials changed
   how much the models believed, not how well.
2. **Baseline ceiling.** Report the pre-registered inflation tests as not testable, and the
   full-sample results as the informative ones (`results_summary.md`, "Baseline (C0) and the
   C0-ceiling rule"). Appendix A has the limitation.
3. **Scope accuracy is exploratory and unvalidated** (one judge, no cross-check). Keep that label
   wherever a scope-accuracy number, table, figure or example is cited, and say that H3 was not
   tested.
4. **Exploratory analyses.** Three were added after the data were seen: the robustness checks, the
   interpreter's discrimination index, and H5. Cite them only as exploratory.
5. **Qwen.** Its parse failures (11.0%; 15.8% against 7.9% with and without the interpreter on C1
   and C2) are a caveat on its H4 result. The slot text carries it.
6. **Power.** With 10 real-obscure pairs, use the CIs, not "no effect".
7. **Submission checklist:** RUNBOOK §14, including every `[verify]` reference.

## File map

| Path | Contents |
|---|---|
| `PREREGISTRATION.md`, `DEVIATIONS.md` | The plan and its tests; every change after data collection began |
| `RUNBOOK.md`, `REPORT_DRAFT.md` | How to run the sprint; the report draft with its slots |
| `corpus/` | Claims, condition templates, signer, probes, rendered examples |
| `src/build_documents.py`, `src/prompt_text.py`, `src/output_schema.py` | Prompts and parsing |
| `src/runner.py`, `src/providers/`, `models.yaml` | Study calls (Groq, Gemini), limits, retries, cost, resume; the judge's provider (Adaption) |
| `src/judge.py`, `src/grade.py` | The judge, grading, the re-ask of cut-off judgements, the (unevaluable) agreement gate |
| `src/analyse.py` | The §7 tests, the exploratory analyses, figures, results summary, filled draft |
| `data/raw/`, `data/logs/`, `data/pilot/` | Append-only responses and run logs; the pilot (excluded from analysis) |
| `data/graded/` | Metrics, the judge sample, every judgement and judge attempt |
| `data/results/` | Results, figures, `results_summary.md`, `REPORT_DRAFT.filled.md` |
