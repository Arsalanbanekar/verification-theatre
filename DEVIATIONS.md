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
