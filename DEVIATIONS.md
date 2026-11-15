# Deviations from the pre-registration

This file records changes made after data collection began (with the pilot, 10 Nov 2026), each
with its date, time and reason.

- 11 Nov 2026, 01:31 IST: scope-accuracy judge replaced after the pilot's first run, before the main run, because Gemma was too slow and unreliable; recorded as pre-registration rev 3.4, `PREREGISTRATION.md` §12 (commit `8d4f9fa`).
- 15 Nov 2026, 01:51 IST: two exploratory robustness checks added to `src/analyse.py` after seeing the parse-failure pattern. qwen3.8-27b failed to parse in 106 of 960 cells (11.0%); on C1 and C2 the rate was 15.8% with the interpreter against 7.9% without.
  1. Every primary comparison re-run on the pooled data without qwen3.8-27b.
  2. qwen3.8-27b's primary comparisons re-run with all its parse-failed cells set to accept = false, then to accept = true.

  Both checks are labelled exploratory in `results_summary.md`. The pre-registered handling of parse failures (missing data, no imputation) is unchanged. Reporting added at the same time:
  - the H4 text states that Qwen's own H4 result carries the interpreter-arm parse-failure caveat;
  - a descriptive parse-failure breakdown by condition, with a χ² test, is not used in any pre-registered test.
- 15 Nov 2026, 16:04 IST: degeneracy guard added to `src/analyse.py`. This is a post-data correction, made after seeing the Groq data. Both gpt-oss models accepted every C0 response, and qwen3.8-27b accepted 87–92% depending on claim type. So the pre-registered C0-ceiling rule (§7) left the pooled real-obscure H1 and H2 tests with 2 of 10 pairs. The two C1 − C0 differences were identical (−22.2 points each). The paired t-test therefore had zero variance and returned p = 0 with a zero-width CI, and Holm reported that as significant.
  1. The pre-registered ceiling rule stays the primary analysis. Each test's number of pairs, and the number dropped at the ceiling, is given beside it.
  2. A test with fewer than 3 pairs, or with zero variance in its pair differences, is reported as "not testable". It keeps its descriptive numbers (the mean difference, the number of pairs and the range of the pair differences) but gets no p-value and no CI.
  3. A not-testable test enters its Holm family with p = 1, as an untested H3 already did under rev 3.4. The family stays at eight, and no other test is corrected less strictly. Before this change it could make other tests easier to pass in two ways:
     - A degenerate p = 0 took the first Holm rank, which lowered every other test's multiplier.
     - A test with no pairs dropped out of the family and shrank it. In each gpt-oss model's own scope, where every pair is at the ceiling, H2b and H4 were corrected over 3 tests instead of 8.

     H4 in gemini-3.5-flash-lite's own scope has no interpreter arm by design, and it also enters with p = 1.
  4. The same guard applies to the exploratory H5 Welch test: it is not testable if either claim type has fewer than 3 pairs or zero variance.
  5. The full-sample result is reported beside every primary test, as §7 already required.
     - It is now also reported for the two stratified results that lacked one: H1 on false twins alone, and H5.
     - When a primary test is not testable, `results_summary.md` and the generated report text say so and name the full-sample result as the informative one.
     - Full-sample results are outside the Holm family, so their p-values are unadjusted and labelled as such. The text calls a full-sample difference a change only when its unadjusted p < .05.
  6. Direction is stated as it is. Where the informative result shows lower acceptance under C1 than under C0, the text says H1 is not supported and the effect runs the opposite way. No hypothesis was reworded.
  7. Reporting added at the same time:
     - C0 acceptance per model and claim type, with the pairs at the C0 ceiling in each scope (`results_summary.md`, `c0_acceptance.csv`);
     - a baseline-ceiling limitation in the report (`REPORT_DRAFT.md`, Appendix A, with a new slot);
     - one sentence on this correction in the report's §3.5.

  The exploratory robustness checks (01:51 entry) re-run the same procedure, so they use the guard too. No model or judge call was made for this change, and `data/raw/` was not touched.
- 15 Nov 2026, 23:36 IST: the judge changed before any main-data judging (pre-registration §5, rev 3.4), by the author's decision.
  1. **Provider: OpenRouter → Adaption**, paid from sponsor credits (`ADAPTION_API_KEY`, Python SDK `adaption`, `src/providers/adaption.py`). §5 planned a paid OpenRouter model pinned to one serving provider; Adaption serves its hosted models itself.
  2. **Main judge: `glm-5.2`** (Z.ai), which `client.models.list()` listed on 15 Nov. The author chose it by the §5 criteria:
     - Adaption lists seven models. Four are excluded as Qwen/Alibaba or Google (qwen3.5-397b, qwen3.8-27b, gemma-4-26b-a4b-it, gemma-4-31b-it). That leaves glm-5.2 and two "Flash" variants (glm-5.3-flash, deepseek-v4-flash).
     - glm-5.2 is a named production model, not a router or an Adaption stack.
     - JSON output: Adaption has no JSON mode. The unchanged judge prompt asks for JSON, and the parser validates every reply.
     - Cost: 3.01 sponsor credits for the 600 judgements, above §5's ~$2 guide, which was a budget guide, not a selection criterion. (Reworded on 16 Nov 2026, 00:35 IST, after the judging. The original line, in `3d50f68`, projected about 2.9 credits from the pilot check.)

     The settings were committed in `models.yaml` (`e578ba5`) before any judge call: temperature 0; the provider's default reasoning, since Adaption has no reasoning parameter; at most 4,000 output tokens including reasoning; no seed, since Adaption accepts none. The prompt and the blinding are unchanged (`src/judge.py`).
  3. **The cross-check judge is dropped**, by the author's decision. No second judge scores any response.

  Consequences:
  - The §5 gate (linear-weighted kappa of at least 0.6 between the two judges) cannot be evaluated. Confirmatory H3 is therefore "not tested". It enters the Holm family with p = 1, as §7 (rev 3.4) prescribes for an untested H3, so the family stays at eight.
  - glm-5.2's scope-accuracy scores are reported as exploratory and unvalidated. This covers the 0/1/2 distribution, the share mentioning the credential, the H3 statistic computed from them (unadjusted, outside the Holm family), Figure 3 and the example justifications.
    - Each is labelled so wherever it appears: `results_summary.md`, the CSVs, the figure, and `REPORT_DRAFT.md` §3.4 and §4.5.
    - Appendix A of the report gains a limitation saying so. With one judge, neither the consistency nor the correctness of its scoring is checked.
  - The same change updates:
    - `models.yaml`: the cross-check is marked dropped;
    - `src/grade.py`: a new gate status, "unevaluable";
    - `src/analyse.py`: a new scope-accuracy source, "exploratory";
    - `RUNBOOK.md`: the cross-check leaves the run order;
    - `REPORT_DRAFT.md` and `README.md`.

  The pilot judge check, the format check §5 requires before main-data judging, ran just before this entry (`e64307a`): 10 of 10 scores were valid. It was preceded by one logged test call on the pilot response the check does not use. No main-data response had been judged when this entry was written.
- 16 Nov 2026, 00:36 IST: the judge's output cap is raised for one re-ask of 30 judgements, by the author's decision. In the main judging (15 Nov, 18:30–18:47 UTC), 30 of the 600 replies hit `max_output_tokens` (4,000). glm-5.2 spent the whole cap on reasoning and returned no score ("incomplete: max_output_tokens"). The pilot check had not shown this: its longest reply used 3,043 tokens.
  1. Those 30 responses, and only those, are re-asked once with `max_output_tokens` raised to 12,000 (`judges.main.rejudge` in `models.yaml`, run by `grade.py --rejudge-truncated`). The prompt, model and temperature are unchanged.
  2. Nothing else is re-judged: the 570 valid judgements stand.
  3. The new rows are appended to `judge_main.jsonl` with stage `rejudge`. The truncated rows stay on disk, and the analysis uses each response's latest judgement.
  4. A re-asked response that is cut off again, or fails, is not asked a third time and stays missing. If the re-ask cannot run, the 30 are reported as missing (5%).

  Outcome (16 Nov 2026, 00:55 IST; the re-ask ran 19:19–19:25 UTC on 15 Nov, at `5b56656`):
  - All 30 re-asks returned a valid score: 18 scored 0 and 12 scored 1. They used 361 to 5,201 output tokens.
  - Seven gateway time-outs (HTTP 504) were retried within the same re-ask, as transient failures are in the main run. Every attempt is logged.
  - The re-ask cost 0.30 credits, 3.31 in all. All 600 sampled responses now have a valid judgement.
  - At temperature 0 the re-asks did not reproduce the first replies (one finished in 361 tokens). Each re-ask is a fresh judgement with the same prompt, not a continuation.
- 16 Nov 2026, 00:36 IST: one exploratory analysis added to `src/analyse.py` after seeing the H4 result, by the author's decision. It asks whether the interpreter improves accuracy or only lowers acceptance across the board.
  - It compares the discrimination index (acceptance of the true twin minus the false twin) on C1 and C2, with and without the interpreter. This is computed per interpreter-arm model and pooled over them, beside the true and false acceptance it comes from (`interpreter_discrimination.csv`).
  - It is labelled exploratory wherever it appears (`results_summary.md`, and a new slot in `REPORT_DRAFT.md` §4.7).
  - It is outside the Holm family, so its p-values are unadjusted. It draws on its own random stream, so no other result changes.
