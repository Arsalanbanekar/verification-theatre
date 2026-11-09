# Deviations from the pre-registration

`PREREGISTRATION.md` (rev 3.2, commit `a56281d`) is the plan. Anything done differently once data
collection begins on 13 Nov 2026 is listed here, with the date, time and reason, before the change
is made (CLAUDE.md). Changes decided before any data are in the pre-registration's revision
history (§12).

## Deviations

None so far (9 Nov 2026, before any data).

| # | When (IST) | What changed | Why | Effect on the analysis |
|---|---|---|---|---|

## Analysis details fixed before any data (not deviations)

The pre-registration leaves the following open. They were fixed in `src/analyse.py` on 9 Nov 2026,
before any data existed, and are listed here so they are visible and dated.

1. **Tests.** Primary: paired t-tests over twin pairs, two-sided, with 95% t-intervals (one-sample
   for H3, Welch for H5). Robustness: sign-flip permutation tests on the same pair differences,
   reported alongside. With 10 pairs the exact permutation test cannot go below p = 2/1024, which is
   why it is the check rather than the primary.
2. **Holm family.** The six primary comparisons (§7) contain eight tests:
   - H1: C1 vs C0 acceptance;
   - H2: C3 vs C2 acceptance, C3 vs C2 confidence, C4 vs C1 acceptance, C4 vs C3 acceptance;
   - H2b: discrimination index, C5 vs C0;
   - H3: scope accuracy;
   - H4: interpreter vs none.

   Holm runs over all eight, which is at least as strict as over six. It is applied separately in
   each reporting scope (pooled, and each model) and each claim-type set.
3. **Pair values.** A claim's value is its mean over reps. A pair's value is the mean of its twins,
   or true minus false for the discrimination index. Pooled results weight each model equally.
4. **C0 ceiling (§7).** Inflation tests (H1, H2, H5) drop pairs whose twins were both accepted in
   every C0 response in that scope. The full-sample result is reported alongside.
5. **H2b.** The test is the C5 vs C0 discrimination index (the positive control). "Flat across
   C0–C4" is shown by the mean of C1–C4 against C0, with its CI, outside the Holm family.
6. **H3, "low".** Fewer than half of the justifications that mention the credential describe its
   scope correctly (score 2). The test uses pair-level shares against 50%; justifications scored
   NA (no mention) are excluded.
7. **H4.** Interpreter minus no interpreter on C1 and C2 pooled, for the three interpreter-arm
   models, over all pairs.
8. **H5 (exploratory).** C1 − C0 on invented pairs minus the same on real-obscure pairs, with
   C0-ceiling pairs dropped. Welch t-test, unadjusted, outside the Holm family.
9. **Headline numbers.** The real-obscure half for H1–H3 and H2b (rev 3), all pairs for H4. The
   invented half is reported separately throughout.
