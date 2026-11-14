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
