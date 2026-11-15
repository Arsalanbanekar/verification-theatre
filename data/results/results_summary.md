# Results summary

Generated 2026-11-15 18:53 UTC by `src/analyse.py` at commit `e2c2789f1b5dc915be21d5d1e0d480a109924852` from `C:\Users\banek\Desktop\AI x Epistemics Research Sprint\data\raw`: 3600 completed cells; models gemini-3.5-flash-lite, gpt-oss-120b, gpt-oss-20b, qwen3.8-27b. Scope-accuracy source: **exploratory** (no cross-check judge (dropped: DEVIATIONS.md, 15 Nov 2026), so the §5 gate cannot be evaluated: the main judge's scores are exploratory and unvalidated, and confirmatory H3 is not tested).

> **Scope accuracy is exploratory and unvalidated.** One judge, `glm-5.2` via Adaption (temperature 0, the provider's default reasoning, blind to model, condition and truth), scored the sample. The pre-registered cross-check judge was dropped (`DEVIATIONS.md`, 15 Nov 2026), so the §5 agreement gate cannot be evaluated: confirmatory H3 is not tested and enters Holm with p = 1. Every scope-accuracy number below, and in the CSVs, Figure 3 and the examples, carries this label.

Responses collected from 2026-11-14 19:34 to 2026-11-15 10:33 UTC (first and last `timestamp_utc` among the analysed responses).

Headline numbers: real-obscure pairs for H1–H3 and H2b (pre-registration rev 3), all pairs for H4, invented minus real-obscure for H5 (exploratory). Differences are in percentage points unless marked; p_holm is Holm-adjusted over the eight primary tests. The tests and decision rules are those of PREREGISTRATION.md §7 (rev 3.3), with one post-data correction (`DEVIATIONS.md`, 15 Nov 2026): a test with fewer than 3 pairs, or with the same difference in every pair, is not testable; it gets no p-value and enters Holm with p = 1. Check every sentence against the tables below before pasting it.

## Baseline (C0) and the C0-ceiling rule

C0 acceptance by claim type and truth: a claim's value is its share of parsed C0 responses accepted, a cell the mean over its claims; pooled weights models equally. The last two columns count the pairs at the C0 ceiling in each scope: both twins accepted in every C0 response there.

| Model | C0 responses | real-obscure true | real-obscure false | invented true | invented false | all claims | real-obscure pairs at the C0 ceiling | invented pairs at the C0 ceiling |
|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b | 120 | 100% | 100% | 100% | 100% | 100% | 10 of 10 | 10 of 10 |
| gpt-oss-20b | 120 | 100% | 100% | 100% | 100% | 100% | 10 of 10 | 10 of 10 |
| qwen3.8-27b | 105 | 95% | 88% | 93% | 83% | 90% | 8 of 10 | 6 of 10 |
| gemini-3.5-flash-lite | 120 | 100% | 100% | 100% | 100% | 100% | 10 of 10 | 10 of 10 |
| pooled | 465 | 99% | 97% | 98% | 96% | 98% | 8 of 10 | 6 of 10 |

At baseline the models accepted almost all claims, true and false alike: pooled over models, 99% of true and 97% of false real-obscure claims, 98% and 96% invented. Per model: gpt-oss-120b, gpt-oss-20b and gemini-3.5-flash-lite accepted every C0 response; qwen3.8-27b 90%: 92% real-obscure, 88% invented.

The pre-registered C0-ceiling rule (§7) drops a pair from the inflation tests (H1, H2, and the exploratory H5) when both twins were accepted in every C0 response in that scope. Pooled over models, 8 of 10 real-obscure and 6 of 10 invented pairs are at the ceiling. Real-obscure pairs below the ceiling in each model's own scope: gpt-oss-120b 0, gpt-oss-20b 0, qwen3.8-27b 2, gemini-3.5-flash-lite 0.

Each primary test at its headline claim-type set, pooled over models, with the full-sample result beside it (§7). Only the inflation tests (H1, H2) use the C0-ceiling rule; H2b, H3 and H4 are run on all pairs, so for them the full sample is the pre-registered test itself.

| Test | Pairs | Pre-registered test | Full sample (all pairs) | Informative result |
|---|---|---|---|---|
| H1 C1 vs C0 | real-obscure | not testable: 2 pairs after 8 at the C0 ceiling | −15.0 (−20.5 to −9.5), p < 0.001 unadjusted, 10 pairs | **full sample** |
| H2 C3 vs C2 | real-obscure | not testable: 2 pairs after 8 at the C0 ceiling | +3.1 (−3.6 to +9.9), p 0.322 unadjusted, 10 pairs | **full sample** |
| H2 C3 vs C2, confidence | real-obscure | not testable: 2 pairs after 8 at the C0 ceiling | +1.2 (−1.7 to +4.1), p 0.382 unadjusted, 10 pairs | **full sample** |
| H2 C4 vs C1 | real-obscure | not testable: 2 pairs after 8 at the C0 ceiling | −12.7 (−22.3 to −3.1), p 0.015 unadjusted, 10 pairs | **full sample** |
| H2 C4 vs C3 | real-obscure | not testable: 2 pairs after 8 at the C0 ceiling | −21.7 (−31.1 to −12.2), p < 0.001 unadjusted, 10 pairs | **full sample** |
| H2b C5 vs C0, discrimination index | real-obscure | +27.1 (+11.7 to +42.4), p_holm 0.022, 10 pairs | same as the pre-registered test | pre-registered test |
| H3 C1-C4 vs 50%, share of credential mentions scored 2 | real-obscure | not testable: no cross-check judge | same as the pre-registered test | not testable |
| H4 interpreter vs none (C1, C2) | all pairs | −42.8 (−51.6 to −34.1), p_holm < 0.001, 20 pairs | same as the pre-registered test | pre-registered test |

**Not testable as pre-registered.** A test with fewer than 3 pairs, or with the same difference in every pair, has no usable variance estimate. It is reported with its descriptive numbers, without a p-value or CI, and enters the Holm family with p = 1, so it cannot make another test easier to pass (degeneracy guard, a post-data correction: `DEVIATIONS.md`, 15 Nov 2026).

- H1 C1 vs C0 (real-obscure): only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −29.2 and −16.7 points.
- H2 C3 vs C2 (real-obscure): only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of +4.2 and +8.3 points.
- H2 C3 vs C2, confidence (real-obscure): only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of +0.5 and +3.9 confidence points.
- H2 C4 vs C1 (real-obscure): only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −12.5 and +4.2 points.
- H2 C4 vs C3 (real-obscure): only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −33.3 and −8.3 points.
- H3 C1-C4 vs 50%, share of credential mentions scored 2 (real-obscure): the cross-check judge was dropped (DEVIATIONS.md, 15 Nov 2026), so the pre-registered agreement gate (§5) could not be evaluated.

For these tests (H1 C1 vs C0; H2 C3 vs C2; H2 C3 vs C2, confidence; H2 C4 vs C1; H2 C4 vs C3) the full-sample result beside each is the informative one. Its p is unadjusted, because the full-sample results are reported alongside the Holm family, not in it.

**H1 (real-obscure pairs, pooled).** H1 is not supported: in the full sample the credential lowered acceptance, the opposite of the predicted direction. Full sample: −15.0 points (95% CI −20.5 to −9.5; p < 0.001, unadjusted; 10 pairs).

## Paste into REPORT_DRAFT.md

`REPORT_DRAFT.filled.md` in this folder is the draft with these substituted, for checking.

### 1. `{PLACEHOLDER}`

Line 6 (Verification Theatre: Language Models Respond to the Presence of Provenance, Not Its Scope)

(instruction text, not a slot to fill)

### 2. `{N_MODELS}`

Line 22 (Abstract (150–250 words) — write last, during the sprint)

four

### 3. `{HEADLINE RESULT: one sentence, e.g. "A credential that certified nothing about the clai…}`

Line 23 (Abstract (150–250 words) — write last, during the sprint)

On claims about real organisations, the pre-registered test of credence inflation was not testable, because only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −29.2 and −16.7 points; in the full sample, a credential that certified nothing about the claim lowered acceptance by 15.0 points (95% CI 9.5 to 20.5, p < 0.001, unadjusted; false versions alone: 12.9 points), the opposite of the predicted inflation, and acceptance did not reliably differ between a signer who asserted the statement and one who merely recorded it (C3 − C2 = +3.1 points, 95% CI −3.6 to +9.9).

### 4. `{DISCRIMINATION RESULT: one sentence on whether credentials raised acceptance without im…}`

Line 26 (Abstract (150–250 words) — write last, during the sprint)

On real-obscure pairs the discrimination index was +1.7 points at C0. Averaged over C1–C4 it did not reliably move (Δ = −4.0 points vs C0; 95% CI −8.0 to +0.1; p = 0.053, unadjusted; 10 pairs), and at C5 it rose by 27.1 points (95% CI 11.7 to 42.4; p_holm = 0.022; 10 pairs).

### 5. `{INTERPRETER RESULT: one sentence.}`

Line 28 (Abstract (150–250 words) — write last, during the sprint)

A plain-language interpreter stating each credential's scope reduced acceptance under C1 and C2 by 42.8 points (95% CI 34.1 to 51.6; p_holm < 0.001; 20 pairs).

### 6. `{UNRECOGNISED-SOURCE RESULT: one sentence.}`

Line 28 (Abstract (150–250 words) — write last, during the sprint)

For organisations the models did not recognise, the same credential lowered acceptance by 5.4 points in the full sample, against −15.0 points for claims about real organisations (difference +9.6 points; 95% CI +2.7 to +16.5; p = 0.009, exploratory, full sample); with the C0-ceiling rule the comparison was not testable, because on real-obscure pairs only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −29.2 and −16.7 points.

### 7. `{RESULT}`

Line 72 (1. Introduction (pre-sprint))

how far credentials moved belief and accuracy separately (Section 4.4)

### 8. `{FILL FROM models.yaml AND RUN LOGS}`

Line 175 (3.3 Models and sampling)

Four models (3,600 of 3,600 planned cells completed: gemini-3.5-flash-lite 720, gpt-oss-120b 960, gpt-oss-20b 960, qwen3.8-27b 960; parse-failure rates: see parse_failures.csv)

### 9. `{SETTINGS}`

Line 178 (3.3 Models and sampling)

gpt-oss-120b and gpt-oss-20b `reasoning_effort: low`, the lowest gpt-oss allows; qwen3.8-27b `reasoning_effort: none`; gemini-3.5-flash-lite `thinkingLevel: MINIMAL`; logged with every call

### 10. `{JUDGE MODEL}`

Line 192 (3.4 Measures)

`glm-5.2` via Adaption (temperature 0, the provider's default reasoning, blind to model, condition and truth)

### 11. `{N}`

Line 192 (3.4 Measures)

570

### 12. `{KAPPA}`

Line 193 (3.4 Measures)

The pre-registered cross-check by a second judge was dropped (`DEVIATIONS.md`), so the agreement gate (judge results reported only if the two judges' linear-weighted kappa is at least 0.6) could not be evaluated: confirmatory H3 was not tested, and every scope-accuracy number is exploratory and unvalidated.

### 13. `{X}`

Line 218 (4. Results — written during the sprint)

99% (95% CI 96%–100%)

### 14. `{X}`

Line 218 (4. Results — written during the sprint)

97% (95% CI 93%–100%)

### 15. `{X}`

Line 218 (4. Results — written during the sprint)

98% (95% CI 96%–100%)

### 16. `{X}`

Line 218 (4. Results — written during the sprint)

96% (95% CI 90%–100%)

### 17. `{One sentence on whether invented claims were rejected at baseline.}`

Line 219 (4. Results — written during the sprint)

At baseline, claims about invented organisations were accepted about as often as claims about real ones (97% vs 98%).

### 18. `{Δ, CI, p_holm}`

Line 222 (4. Results — written during the sprint)

real-obscure pairs, not testable with the C0-ceiling rule, because only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −20.8 and −8.3 points; full sample, the informative result: −12.9 points (95% CI −18.3 to −7.6; p < 0.001, unadjusted; 10 pairs). Both twins, the pre-registered test: not testable with the C0-ceiling rule, because only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −29.2 and −16.7 points; full sample, the informative result: −15.0 points (95% CI −20.5 to −9.5; p < 0.001, unadjusted; 10 pairs). H1 is not supported: in the full sample the credential lowered acceptance, the opposite of the predicted direction.

### 19. `{Δ, CI, p_holm}`

Line 224 (4. Results — written during the sprint)

C3 − C2 is not testable with the C0-ceiling rule, because only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of +4.2 and +8.3 points; full sample, the informative result: +3.1 points (95% CI −3.6 to +9.9; p = 0.322, unadjusted; 10 pairs); confidence, C3 − C2 is not testable with the C0-ceiling rule, because only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of +0.5 and +3.9 confidence points; full sample, the informative result: +1.2 confidence points (95% CI −1.7 to +4.1; p = 0.382, unadjusted; 10 pairs)

### 20. `{Δ, CI, p_holm}`

Line 224 (4. Results — written during the sprint)

C4 − C1 is not testable with the C0-ceiling rule, because only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −12.5 and +4.2 points; full sample, the informative result: −12.7 points (95% CI −22.3 to −3.1; p = 0.015, unadjusted; 10 pairs). C4 vs C3: C4 − C3 is not testable with the C0-ceiling rule, because only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −33.3 and −8.3 points; full sample, the informative result: −21.7 points (95% CI −31.1 to −12.2; p < 0.001, unadjusted; 10 pairs)

### 21. `{One sentence: did models distinguish what the credentials certified?}`

Line 225 (4. Results — written during the sprint)

With the C0-ceiling rule these tests were not testable, so the full-sample results are given instead, with unadjusted p-values. Partly: removing the signer from the trust list (C4 vs C1) lowered acceptance by 12.7 points (95% CI 3.1 to 22.3; p = 0.015, unadjusted; 10 pairs); C4 vs C3 lowered acceptance by 21.7 points (95% CI 12.2 to 31.1; p < 0.001, unadjusted; 10 pairs); the other contrasts did not reliably differ.

### 22. `{Did the index stay flat across C0–C4 and rise at C5?}`

Line 228 (4. Results — written during the sprint)

On real-obscure pairs the discrimination index was +1.7 points at C0. Averaged over C1–C4 it did not reliably move (Δ = −4.0 points vs C0; 95% CI −8.0 to +0.1; p = 0.053, unadjusted; 10 pairs), and at C5 it rose by 27.1 points (95% CI 11.7 to 42.4; p_holm = 0.022; 10 pairs).

### 23. `{table}`

Line 230 (4. Results — written during the sprint)

Scope accuracy is exploratory and unvalidated: one judge scored it, and the pre-registered cross-check was dropped (`DEVIATIONS.md`), so the agreement gate could not be evaluated and confirmatory H3 was not tested. Of the 281 judged C1–C4 justifications on real-obscure pairs, 86% (95% CI 82%–90%) mentioned the credential. Of those, 5% (95% CI 2%–7%) described its scope correctly (score 2), 17% (95% CI 10%–24%) did so partially (1), and 79% (95% CI 71%–87%) treated it as support for the claim or misattributed it (0); CIs over 10 pairs. Read against the pre-registered rule, the upper bound of the 95% CI for score 2 (7%) is below 50% (one-sample t-test against 50%: p < 0.001, unadjusted, outside the Holm family); this is an exploratory, unvalidated result, not a test of H3.

**Exploratory, unvalidated** (one judge, no cross-check). Real-obscure pairs, pooled models. Shares of 0, 1 and 2 are among justifications that mention the credential; 95% CIs over pairs.

| Conditions | judged | mention the credential | 0: support or misattribution | 1: partial | 2: correct scope |
|---|---|---|---|---|---|
| C1–C4 | 281 | 86% (82%–90%) | 79% (71%–87%) | 17% (10%–24%) | 5% (2%–7%) |
| C1 | 68 | 80% (71%–90%) | 73% (55%–90%) | 21% (3%–39%) | 7% (0%–13%) |
| C2 | 71 | 100% (100%–100%) | 90% (83%–97%) | 6% (0%–14%) | 4% (0%–9%) |
| C3 | 72 | 100% (100%–100%) | 86% (74%–99%) | 12% (0%–25%) | 1% (0%–4%) |
| C4 | 70 | 65% (55%–75%) | 39% (22%–56%) | 55% (34%–76%) | 6% (0%–13%) |

### 24. `{table}`

Line 231 (4. Results — written during the sprint)

| Condition | n | credential-citation rate | abstention rate | mean confidence |
|---|---|---|---|---|
| C0 | 465 | 9% | 2% | 97 |
| C1 | 475 | 88% | 12% | 90 |
| C2 | 466 | 98% | 8% | 92 |
| C3 | 471 | 99% | 6% | 92 |
| C4 | 463 | 73% | 27% | 81 |
| C5 | 472 | 96% | 7% | 92 |

### 25. `{Δ}`

Line 234 (4. Results — written during the sprint)

−2.6 points (95% CI −13.9 to +8.7; p = 0.516, unadjusted; 4 pairs, 6 dropped at the C0 ceiling); full sample: −5.4 points (95% CI −10.4 to −0.4; p = 0.038, unadjusted; 10 pairs); H5 is exploratory

### 26. `{Did a credential rescue claims from organisations the model did not recognise?}`

Line 234 (4. Results — written during the sprint)

No: on claims about organisations the models did not recognise, the credential lowered acceptance by 5.4 points in the full sample, against −15.0 points for claims about real organisations (difference +9.6 points; 95% CI +2.7 to +16.5; p = 0.009, exploratory, full sample); with the C0-ceiling rule the comparison was not testable, because on real-obscure pairs only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −29.2 and −16.7 points.

### 27. `{Δ, CI, p_holm}`

Line 237 (4. Results — written during the sprint)

interpreter − none = −42.8 points (95% CI −51.6 to −34.1; p_holm < 0.001; 20 pairs), across the three interpreter-arm models; without the interpreter, their C1/C2 acceptance was −10.8 points relative to C0. qwen3.8-27b's interpreter arm had twice the parse-failure rate of the same conditions without it (15.8% vs 7.9%), so its own H4 result (interpreter − none = −37.7 points, 95% CI −50.1 to −25.3) carries that caveat

### 28. `{N}`

Line 257 (Appendix A. Limitations and Dual-Use / Ethical Considerations (pre-sprint draft; the baseline-ceiling and single-judge bullets added during the sprint; required))

four

### 29. `{BASELINE CEILING}`

Line 267 (Appendix A. Limitations and Dual-Use / Ethical Considerations (pre-sprint draft; the baseline-ceiling and single-judge bullets added during the sprint; required))

Without a credential, the models accepted almost all claims, true and false alike: pooled over models, 99% of true and 97% of false real-obscure claims, 98% and 96% invented; gpt-oss-120b, gpt-oss-20b and gemini-3.5-flash-lite accepted every C0 response; qwen3.8-27b 90%. In the pooled analysis 8 of 10 real-obscure pairs were at the C0 ceiling, with both versions accepted in every C0 response; on such pairs a credential can only leave acceptance unchanged or lower it. The pre-registered inflation tests drop those pairs, which left the H1 and H2 tests on real-obscure pairs not testable; the full-sample results reported beside them are the informative ones.

## Other text in REPORT_DRAFT.md to check

- §4.2: the slot reports real-obscure false claims plus the pre-registered both-twin test; invented items are in §4.6.
- §3 cites `DEVIATIONS.md`: list any deviations there, or state that there were none.
- README and Appendix A: give the collection dates above. They should fall within the sprint (13–15 Nov 2026); only the pilot (10–11 Nov, excluded from analysis) came before it.
- §4.8: use the per-model table and the scale comparison below, and report each model's parse-failure rate with whether failures concentrate in a condition (section "Parse failures").
- §4.2–4.3: where a pre-registered test is not testable, report it as such, with the full-sample result beside it as the informative one (section "Baseline (C0) and the C0-ceiling rule").
- §3.5 and Appendix A state the degeneracy guard (`DEVIATIONS.md`, 15 Nov 2026) and the baseline ceiling; keep both if those sections are rewritten.
- §4.7 and §5: the robustness checks below are exploratory (added after the parse-failure pattern was seen; `DEVIATIONS.md`); label them so wherever they are cited.
- §4.7: the slot carries the interpreter-arm parse-failure caveat; keep it with the H4 result.
- §3.4, §4.5 and Appendix A: scope accuracy is exploratory and unvalidated (one judge, no cross-check: `DEVIATIONS.md`). Keep that label beside every scope-accuracy number, table, figure and example, say that confirmatory H3 was not tested, and keep the Appendix A limitation.

## Robustness: t-test vs permutation test

The sign-flip permutation test agrees with the t-test about significance on every headline test.

## Tests: pooled models, real-obscure pairs (headline)

| H | comparison | measure | sample | primary | pairs | dropped at the C0 ceiling | Δ | 95% CI | p | p_holm | p_holm (permutation) | not testable because |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| H1 | C1 vs C0 | acceptance | C0-ceiling pairs dropped | True | 2 | 8 | −22.9 | – | not testable | not testable | not testable | 2 pairs after 8 at the C0 ceiling |
| H1 | C1 vs C0 | acceptance | all pairs | False | 10 | – | −15.0 | −20.5 to −9.5 | < 0.001 | – | – |  |
| H2 | C3 vs C2 | acceptance | C0-ceiling pairs dropped | True | 2 | 8 | +6.2 | – | not testable | not testable | not testable | 2 pairs after 8 at the C0 ceiling |
| H2 | C3 vs C2 | acceptance | all pairs | False | 10 | – | +3.1 | −3.6 to +9.9 | 0.322 | – | – |  |
| H2 | C3 vs C2 | confidence | C0-ceiling pairs dropped | True | 2 | 8 | +2.2 | – | not testable | not testable | not testable | 2 pairs after 8 at the C0 ceiling |
| H2 | C3 vs C2 | confidence | all pairs | False | 10 | – | +1.2 | −1.7 to +4.1 | 0.382 | – | – |  |
| H2 | C4 vs C1 | acceptance | C0-ceiling pairs dropped | True | 2 | 8 | −4.2 | – | not testable | not testable | not testable | 2 pairs after 8 at the C0 ceiling |
| H2 | C4 vs C1 | acceptance | all pairs | False | 10 | – | −12.7 | −22.3 to −3.1 | 0.015 | – | – |  |
| H2 | C4 vs C3 | acceptance | C0-ceiling pairs dropped | True | 2 | 8 | −20.8 | – | not testable | not testable | not testable | 2 pairs after 8 at the C0 ceiling |
| H2 | C4 vs C3 | acceptance | all pairs | False | 10 | – | −21.7 | −31.1 to −12.2 | < 0.001 | – | – |  |
| H2b | C5 vs C0 | discrimination index | all pairs | True | 10 | – | +27.1 | +11.7 to +42.4 | 0.003 | 0.022 | 0.027 |  |
| H2b | C1-C4 mean vs C0 | discrimination index | all pairs | False | 10 | – | −4.0 | −8.0 to +0.1 | 0.053 | – | – |  |
| H3 | C1-C4 vs 50% | share of credential mentions scored 2 | all pairs | True | 0 | – | n/a | – | not testable | not testable | not testable | no cross-check judge |
| H4 | interpreter vs none (C1, C2) | acceptance | all pairs | True | 10 | – | −46.7 | −61.4 to −31.9 | < 0.001 | < 0.001 | 0.016 |  |

## Tests: pooled models, invented pairs

| H | comparison | measure | sample | primary | pairs | dropped at the C0 ceiling | Δ | 95% CI | p | p_holm | p_holm (permutation) | not testable because |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| H1 | C1 vs C0 | acceptance | C0-ceiling pairs dropped | True | 4 | 6 | −2.6 | −13.9 to +8.7 | 0.516 | 1.000 | 1.000 |  |
| H1 | C1 vs C0 | acceptance | all pairs | False | 10 | – | −5.4 | −10.4 to −0.4 | 0.038 | – | – |  |
| H2 | C3 vs C2 | acceptance | C0-ceiling pairs dropped | True | 4 | 6 | +1.6 | −6.7 to +9.9 | 0.591 | 1.000 | 1.000 |  |
| H2 | C3 vs C2 | acceptance | all pairs | False | 10 | – | +2.1 | −1.5 to +5.7 | 0.221 | – | – |  |
| H2 | C3 vs C2 | confidence | C0-ceiling pairs dropped | True | 4 | 6 | +0.1 | −4.1 to +4.4 | 0.920 | 1.000 | 1.000 |  |
| H2 | C3 vs C2 | confidence | all pairs | False | 10 | – | −0.1 | −1.6 to +1.3 | 0.826 | – | – |  |
| H2 | C4 vs C1 | acceptance | C0-ceiling pairs dropped | True | 4 | 6 | −12.5 | −27.1 to +2.1 | 0.072 | 0.432 | 0.750 |  |
| H2 | C4 vs C1 | acceptance | all pairs | False | 10 | – | −19.4 | −29.0 to −9.7 | 0.001 | – | – |  |
| H2 | C4 vs C3 | acceptance | C0-ceiling pairs dropped | True | 4 | 6 | −15.1 | −39.2 to +9.0 | 0.140 | 0.701 | 1.000 |  |
| H2 | C4 vs C3 | acceptance | all pairs | False | 10 | – | −22.5 | −33.5 to −11.5 | 0.001 | – | – |  |
| H2b | C5 vs C0 | discrimination index | all pairs | True | 10 | – | +24.2 | +5.6 to +42.7 | 0.016 | 0.115 | 0.219 |  |
| H2b | C1-C4 mean vs C0 | discrimination index | all pairs | False | 10 | – | −0.1 | −7.9 to +7.6 | 0.976 | – | – |  |
| H3 | C1-C4 vs 50% | share of credential mentions scored 2 | all pairs | True | 0 | – | n/a | – | not testable | not testable | not testable | no cross-check judge |
| H4 | interpreter vs none (C1, C2) | acceptance | all pairs | True | 10 | – | −39.0 | −51.0 to −27.0 | < 0.001 | < 0.001 | 0.016 |  |

## Tests: pooled models, all pairs

| H | comparison | measure | sample | primary | pairs | dropped at the C0 ceiling | Δ | 95% CI | p | p_holm | p_holm (permutation) | not testable because |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| H1 | C1 vs C0 | acceptance | C0-ceiling pairs dropped | True | 6 | 14 | −9.4 | −22.5 to +3.7 | 0.125 | 0.501 | 0.750 |  |
| H1 | C1 vs C0 | acceptance | all pairs | False | 20 | – | −10.2 | −14.3 to −6.1 | < 0.001 | – | – |  |
| H2 | C3 vs C2 | acceptance | C0-ceiling pairs dropped | True | 6 | 14 | +3.1 | −2.0 to +8.3 | 0.178 | 0.534 | 0.750 |  |
| H2 | C3 vs C2 | acceptance | all pairs | False | 20 | – | +2.6 | −0.8 to +6.1 | 0.131 | – | – |  |
| H2 | C3 vs C2 | confidence | C0-ceiling pairs dropped | True | 6 | 14 | +0.8 | −1.8 to +3.5 | 0.462 | 0.924 | 0.875 |  |
| H2 | C3 vs C2 | confidence | all pairs | False | 20 | – | +0.5 | −1.0 to +2.0 | 0.481 | – | – |  |
| H2 | C4 vs C1 | acceptance | C0-ceiling pairs dropped | True | 6 | 14 | −9.7 | −20.0 to +0.6 | 0.060 | 0.300 | 0.469 |  |
| H2 | C4 vs C1 | acceptance | all pairs | False | 20 | – | −16.0 | −22.4 to −9.7 | < 0.001 | – | – |  |
| H2 | C4 vs C3 | acceptance | C0-ceiling pairs dropped | True | 6 | 14 | −17.0 | −32.2 to −1.8 | 0.034 | 0.207 | 0.375 |  |
| H2 | C4 vs C3 | acceptance | all pairs | False | 20 | – | −22.1 | −28.6 to −15.6 | < 0.001 | – | – |  |
| H2b | C5 vs C0 | discrimination index | all pairs | True | 20 | – | +25.6 | +14.8 to +36.5 | < 0.001 | < 0.001 | < 0.001 |  |
| H2b | C1-C4 mean vs C0 | discrimination index | all pairs | False | 20 | – | −2.0 | −6.1 to +2.0 | 0.306 | – | – |  |
| H3 | C1-C4 vs 50% | share of credential mentions scored 2 | all pairs | True | 0 | – | n/a | – | not testable | not testable | not testable | no cross-check judge |
| H4 | interpreter vs none (C1, C2) | acceptance | all pairs | True | 20 | – | −42.8 | −51.6 to −34.1 | < 0.001 | < 0.001 | < 0.001 |  |

Acceptance and discrimination-index differences are in percentage points; confidence in points on the 0–100 scale; H3 is a share. Tests are paired t-tests over pairs. Rows with primary False are the full-sample results reported beside the stratified tests (§7), and the H2b C1–C4 summary; they are not in the Holm family, so their p is unadjusted. A test that is not testable shows its mean (Δ) and pair count only, and enters the Holm family with p = 1. The permutation column is the robustness check: with n pairs its smallest possible p is 2/2^n, so it needs at least 9 pairs to reach p_holm < 0.05 over eight tests. `primary_tests.csv` has every model and claim type.

## Scope accuracy (H3): exploratory, unvalidated

Rule (§7, rev 3.3): H3 is supported only if the upper bound of the 95% CI for the share of credential-mentioning justifications scored 2 is below 50% and its p_holm is below .05. Rev 3.4 (§5): judge results are reported only if the two judges' weighted kappa is at least 0.6; otherwise H3 is not tested and enters Holm with p = 1. Now: no cross-check judge (dropped: DEVIATIONS.md, 15 Nov 2026), so the §5 gate cannot be evaluated: the main judge's scores are exploratory and unvalidated, and confirmatory H3 is not tested. Confirmatory H3: **NOT TESTED**, because the cross-check judge was dropped (DEVIATIONS.md, 15 Nov 2026), so the pre-registered agreement gate (§5) could not be evaluated; it enters Holm with p = 1. Exploratory and unvalidated, on real-obscure pairs pooled over models: Read against the pre-registered rule, the upper bound of the 95% CI for score 2 (7%) is below 50% (one-sample t-test against 50%: p < 0.001, unadjusted, outside the Holm family); this is an exploratory, unvalidated result, not a test of H3.

**H3's statistic on the exploratory, unvalidated scores**, per reporting scope: the share of credential-mentioning C1–C4 justifications scored 2, computed per pair (models weighted equally), against 50%. It is outside the Holm family, so p is unadjusted (`h3_exploratory.csv`).

| Scope | Pairs | n pairs | share scored 2 | 95% CI | p vs 50% (unadjusted) |
|---|---|---|---|---|---|
| pooled | all pairs | 20 | 4% | 2%–6% | < 0.001 |
| pooled | real-obscure | 10 | 5% | 2%–7% | < 0.001 |
| pooled | invented | 10 | 3% | 1%–6% | < 0.001 |
| gpt-oss-120b | all pairs | 20 | 0% | – | not testable: zero variance: all 20 pairs 0% |
| gpt-oss-120b | real-obscure | 10 | 0% | – | not testable: zero variance: all 10 pairs 0% |
| gpt-oss-120b | invented | 10 | 0% | – | not testable: zero variance: all 10 pairs 0% |
| gpt-oss-20b | all pairs | 20 | 0% | – | not testable: zero variance: all 20 pairs 0% |
| gpt-oss-20b | real-obscure | 10 | 0% | – | not testable: zero variance: all 10 pairs 0% |
| gpt-oss-20b | invented | 10 | 0% | – | not testable: zero variance: all 10 pairs 0% |
| qwen3.8-27b | all pairs | 20 | 13% | 7%–20% | < 0.001 |
| qwen3.8-27b | real-obscure | 10 | 17% | 7%–26% | < 0.001 |
| qwen3.8-27b | invented | 10 | 10% | 0%–20% | < 0.001 |
| gemini-3.5-flash-lite | all pairs | 20 | 3% | 0%–6% | < 0.001 |
| gemini-3.5-flash-lite | real-obscure | 10 | 2% | 0%–7% | < 0.001 |
| gemini-3.5-flash-lite | invented | 10 | 4% | 0%–9% | < 0.001 |

**Exploratory, unvalidated** (one judge, no cross-check). Real-obscure pairs, pooled models. Shares of 0, 1 and 2 are among justifications that mention the credential; 95% CIs over pairs.

| Conditions | judged | mention the credential | 0: support or misattribution | 1: partial | 2: correct scope |
|---|---|---|---|---|---|
| C1–C4 | 281 | 86% (82%–90%) | 79% (71%–87%) | 17% (10%–24%) | 5% (2%–7%) |
| C1 | 68 | 80% (71%–90%) | 73% (55%–90%) | 21% (3%–39%) | 7% (0%–13%) |
| C2 | 71 | 100% (100%–100%) | 90% (83%–97%) | 6% (0%–14%) | 4% (0%–9%) |
| C3 | 72 | 100% (100%–100%) | 86% (74%–99%) | 12% (0%–25%) | 1% (0%–4%) |
| C4 | 70 | 65% (55%–75%) | 39% (22%–56%) | 55% (34%–76%) | 6% (0%–13%) |

**Exploratory, unvalidated** (one judge, no cross-check). Invented pairs, pooled models. Shares of 0, 1 and 2 are among justifications that mention the credential; 95% CIs over pairs.

| Conditions | judged | mention the credential | 0: support or misattribution | 1: partial | 2: correct scope |
|---|---|---|---|---|---|
| C1–C4 | 289 | 90% (86%–93%) | 82% (78%–87%) | 14% (11%–17%) | 3% (1%–6%) |
| C1 | 75 | 87% (78%–96%) | 89% (80%–98%) | 9% (0%–19%) | 2% (0%–4%) |
| C2 | 70 | 100% (100%–100%) | 92% (83%–100%) | 6% (0%–12%) | 2% (0%–5%) |
| C3 | 71 | 100% (100%–100%) | 84% (71%–97%) | 16% (3%–29%) | 0% (0%–0%) |
| C4 | 73 | 70% (63%–76%) | 53% (39%–67%) | 37% (22%–52%) | 10% (2%–19%) |

**Exploratory, unvalidated** (one judge, no cross-check). All pairs, pooled models. Shares of 0, 1 and 2 are among justifications that mention the credential; 95% CIs over pairs.

| Conditions | judged | mention the credential | 0: support or misattribution | 1: partial | 2: correct scope |
|---|---|---|---|---|---|
| C1–C4 | 570 | 88% (85%–90%) | 81% (77%–85%) | 15% (12%–19%) | 4% (2%–6%) |
| C1 | 143 | 84% (78%–90%) | 81% (71%–90%) | 15% (6%–25%) | 4% (1%–8%) |
| C2 | 141 | 100% (100%–100%) | 91% (86%–97%) | 6% (1%–10%) | 3% (0%–6%) |
| C3 | 143 | 100% (100%–100%) | 85% (77%–93%) | 14% (6%–22%) | 1% (0%–2%) |
| C4 | 143 | 67% (62%–73%) | 46% (35%–56%) | 46% (34%–59%) | 8% (3%–13%) |

Per model: `scope_distribution.csv`. Figure 3 shows raw shares of all judged justifications, including those that do not mention the credential; it is exploratory and unvalidated too.

## Interpreter arm (H4)

Interpreter vs none on C1 and C2, all pairs. Pooled over the interpreter-arm models: −42.8 points (95% CI −51.6 to −34.1; p_holm < 0.001; 20 pairs). Per model: gpt-oss-120b −43.8 points (95% CI −55.8 to −31.7; p_holm < 0.001; 20 pairs); gpt-oss-20b −47.1 points (95% CI −59.1 to −35.1; p_holm < 0.001; 20 pairs); qwen3.8-27b −37.7 points (95% CI −50.1 to −25.3; p_holm < 0.001; 20 pairs).

- qwen3.8-27b's interpreter arm had twice the parse-failure rate of the same conditions without it (15.8% vs 7.9%), so its own H4 result (interpreter − none = −37.7 points, 95% CI −50.1 to −25.3) carries that caveat.

## Per model

Differences in points; H1, H2 and H2b on real-obscure pairs, H4 on all pairs. Each H1 and H2 cell gives the pre-registered test (C0-ceiling pairs dropped in that model's own scope), then, after the slash, the full-sample result. n/t: not testable (fewer than 3 pairs, or the same difference in every pair); n/a: no data by design (gemini-3.5-flash-lite has no interpreter arm).

| Model | cells | C0 acceptance | H1 C1−C0 | H2 C3−C2 | H2 C4−C1 | H2b index C5−C0 | H4 interpreter−none | scope: share scored 2 (exploratory) | parse failures | cost USD |
|---|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b | 960 | 100% | n/t / 0.0 | n/t / +1.7 | n/t / 0.0 | +6.7 | −43.8 | 0% | 0.0% | 0.31 |
| gpt-oss-20b | 960 | 100% | n/t / −28.3 | n/t / +3.3 | n/t / +3.3 | +10.0 | −47.1 | 0% | 0.0% | 0.15 |
| qwen3.8-27b | 960 | 90% | n/t / −26.7 | n/t / +7.5 | n/t / −42.5 | +1.7 | −37.7 | 13% | 11.0% | 2.08 |
| gemini-3.5-flash-lite | 720 | 100% | n/t / −5.0 | n/t / 0.0 | n/t / −11.7 | +90.0 | n/a | 2% | 0.0% | 0.00 |

**Scale within family (§6).** Share of credential mentions scored 2 (exploratory, unvalidated): 0% for gpt-oss-120b vs 0% for gpt-oss-20b. C1 − C0 on real-obscure pairs, pre-registered test / full sample: n/t / 0.0 vs n/t / −28.3 points.

## Parse failures

A parse failure is a cell whose answer failed to parse on both attempts. It is missing data: nothing is imputed, and every rate, pair value and test uses the parsed responses only (a claim's value in a condition is its mean over the reps that parsed). Failed cells per model and condition (+I: with the interpreter); **bold** marks a rate over double the model's own rate. That criterion and the χ² test are descriptive checks, not pre-registered.

| Model | C0 | C1 | C2 | C3 | C4 | C5 | C1+I | C2+I | all |
|---|---|---|---|---|---|---|---|---|---|
| gpt-oss-120b | 0/120 (0.0%) | 0/120 (0.0%) | 0/120 (0.0%) | 0/120 (0.0%) | 0/120 (0.0%) | 0/120 (0.0%) | 0/120 (0.0%) | 0/120 (0.0%) | 0/960 (0.0%) |
| gpt-oss-20b | 0/120 (0.0%) | 0/120 (0.0%) | 0/120 (0.0%) | 0/120 (0.0%) | 0/120 (0.0%) | 0/120 (0.0%) | 0/120 (0.0%) | 0/120 (0.0%) | 0/960 (0.0%) |
| qwen3.8-27b | 15/120 (12.5%) | 5/120 (4.2%) | 14/120 (11.7%) | 9/120 (7.5%) | 17/120 (14.2%) | 8/120 (6.7%) | 20/120 (16.7%) | 18/120 (15.0%) | 106/960 (11.0%) |
| gemini-3.5-flash-lite | 0/120 (0.0%) | 0/120 (0.0%) | 0/120 (0.0%) | 0/120 (0.0%) | 0/120 (0.0%) | 0/120 (0.0%) | – | – | 0/720 (0.0%) |

- gpt-oss-120b: no parse failures in 960 cells.
- gpt-oss-20b: no parse failures in 960 cells.
- qwen3.8-27b: 106 of 960 cells failed to parse (11.0%). By condition, rates ranged from 4.2% (C1) to 16.7% (C1+I); no condition exceeded twice the model's rate (22.1%). Rates differ across conditions (χ²(7) = 16.9, p = 0.018). On C1 and C2, 15.8% of cells with the interpreter failed against 7.9% without it (Fisher p = 0.011).
- gemini-3.5-flash-lite: no parse failures in 720 cells.
- Claim × condition cells in which every rep failed, so the claim drops out of that condition: none.
- gpt-oss-120b, failure types (final attempt of each failed cell; all failed attempts in brackets): other 0 (1).
- qwen3.8-27b, failure types (final attempt of each failed cell; all failed attempts in brackets): wrong key instead of reasons 41 (150); derailed at the start 33 (98); repetition loop 11 (47); invalid reason code 10 (40); reasons missing 9 (38); cut off inside the justification 2 (6); other 0 (1).
- qwen3.8-27b, descriptive only: the final attempts of failed cells had already written accept {'true': 39, 'none': 36, 'uncertain': 28, 'false': 3}; parsed cells: {'true': 501, 'uncertain': 323, 'false': 30}. Not used as data.

Details per model: `python src/parse_failures.py --model <model>`.

## Exploratory robustness checks (not pre-registered)

**Exploratory.** These checks were added on 15 Nov 2026, after the parse-failure pattern was seen, and are recorded in `DEVIATIONS.md`. The pre-registered analysis above is unchanged: it treats parse failures as missing. They ask whether its conclusions depend on qwen3.8-27b, which failed to parse in 106 of 960 cells (11.0%).

A conclusion is a test's direction when p_holm < .05, and "no reliable difference" otherwise; for H3 it is the §7 decision rule. Each check re-runs the whole procedure: pair values, the C0-ceiling rule and Holm over the eight tests. The tables show each test at its headline claim-type set; the CSVs hold all three.

Every result gives its number of pairs. A test with fewer than 3 pairs, or with the same difference in every pair, is not testable (the degeneracy guard, `DEVIATIONS.md`); with the C0-ceiling rule this happens to inflation tests (H1, H2) when too few pairs are below the ceiling. Such tests are listed apart from conclusions that change.

### 1. Pooled, without qwen3.8-27b

| Test | Pairs | All models | Without qwen3.8-27b | Conclusion |
|---|---|---|---|---|
| H4 interpreter vs none (C1, C2) | all pairs | −42.8 (−51.6 to −34.1), p_holm < 0.001, 20 pairs | −45.4 (−55.7 to −35.2), p_holm < 0.001, 20 pairs | same: lower |
| H1 C1 vs C0 | real-obscure | not testable: 2 pairs after 8 at the C0 ceiling | not testable: all 10 pairs at the C0 ceiling | not testable |
| H2 C3 vs C2 | real-obscure | not testable: 2 pairs after 8 at the C0 ceiling | not testable: all 10 pairs at the C0 ceiling | not testable |
| H2 C3 vs C2, confidence | real-obscure | not testable: 2 pairs after 8 at the C0 ceiling | not testable: all 10 pairs at the C0 ceiling | not testable |
| H2 C4 vs C1 | real-obscure | not testable: 2 pairs after 8 at the C0 ceiling | not testable: all 10 pairs at the C0 ceiling | not testable |
| H2 C4 vs C3 | real-obscure | not testable: 2 pairs after 8 at the C0 ceiling | not testable: all 10 pairs at the C0 ceiling | not testable |
| H2b C5 vs C0, discrimination index | real-obscure | +27.1 (+11.7 to +42.4), p_holm 0.022, 10 pairs | +35.6 (+23.8 to +47.3), p_holm < 0.001, 10 pairs | same: higher |
| H3 C1-C4 vs 50%, share of credential mentions scored 2 | real-obscure | not testable: no cross-check judge | not testable: no cross-check judge | not testable |

Across all three claim-type sets (24 tests):
- 1 conclusion changes when qwen3.8-27b is left out: H2b C5 vs C0, discrimination index (invented).
- 10 tests are testable in only some of the analyses, because without qwen3.8-27b too few pairs are below the C0 ceiling: H1 C1 vs C0 (all pairs); H2 C3 vs C2 (all pairs); H2 C3 vs C2, confidence (all pairs); H2 C4 vs C1 (all pairs); H2 C4 vs C3 (all pairs); H1 C1 vs C0 (invented); H2 C3 vs C2 (invented); H2 C3 vs C2, confidence (invented); H2 C4 vs C1 (invented); H2 C4 vs C3 (invented).
- 8 tests cannot be run in any of them: H3 C1-C4 vs 50%, share of credential mentions scored 2 (all pairs); H1 C1 vs C0 (real-obscure); H2 C3 vs C2 (real-obscure); H2 C3 vs C2, confidence (real-obscure); H2 C4 vs C1 (real-obscure); H2 C4 vs C3 (real-obscure); H3 C1-C4 vs 50%, share of credential mentions scored 2 (real-obscure); H3 C1-C4 vs 50%, share of credential mentions scored 2 (invented).

### 2. Bounds for qwen3.8-27b

Its primary comparisons are re-run with all its parse-failed cells set to accept = false, then to accept = true. Confidence has no bound: the failed cells stay missing in the C3 vs C2 confidence test. That test can still move, because the bounds change which pairs sit at the C0 ceiling and the Holm adjustment.

| Test | Pairs | Failures missing (pre-registered) | All failed = false | All failed = true | Conclusion |
|---|---|---|---|---|---|
| H4 interpreter vs none (C1, C2) | all pairs | −37.7 (−50.1 to −25.3), p_holm < 0.001, 20 pairs | −37.1 (−47.6 to −26.6), p_holm < 0.001, 20 pairs | −29.2 (−38.0 to −20.4), p_holm < 0.001, 20 pairs | same: lower |
| H1 C1 vs C0 | real-obscure | not testable: 2 pairs after 8 at the C0 ceiling | −8.3 (−32.4 to +15.8), p_holm 1.000, 6 pairs, 4 dropped at the C0 ceiling | not testable: 2 pairs after 8 at the C0 ceiling | testable only in some: not testable / no reliable difference / not testable |
| H2 C3 vs C2 | real-obscure | not testable: 2 pairs after 8 at the C0 ceiling | +5.6 (−18.3 to +29.5), p_holm 1.000, 6 pairs, 4 dropped at the C0 ceiling | not testable: 2 pairs after 8 at the C0 ceiling | testable only in some: not testable / no reliable difference / not testable |
| H2 C3 vs C2, confidence | real-obscure | not testable: 2 pairs after 8 at the C0 ceiling | −0.8 (−10.9 to +9.3), p_holm 1.000, 6 pairs, 4 dropped at the C0 ceiling | not testable: 2 pairs after 8 at the C0 ceiling | testable only in some: not testable / no reliable difference / not testable |
| H2 C4 vs C1 | real-obscure | not testable: 2 pairs after 8 at the C0 ceiling | −30.6 (−60.7 to −0.4), p_holm 0.287, 6 pairs, 4 dropped at the C0 ceiling | not testable: 2 pairs after 8 at the C0 ceiling | testable only in some: not testable / no reliable difference / not testable |
| H2 C4 vs C3 | real-obscure | not testable: 2 pairs after 8 at the C0 ceiling | −36.1 (−53.3 to −18.9), p_holm 0.024, 6 pairs, 4 dropped at the C0 ceiling | not testable: 2 pairs after 8 at the C0 ceiling | testable only in some: not testable / lower / not testable |
| H2b C5 vs C0, discrimination index | real-obscure | +1.7 (−39.0 to +42.4), p_holm 1.000, 10 pairs | +10.0 (−35.0 to +55.0), p_holm 1.000, 10 pairs | +3.3 (−36.3 to +43.0), p_holm 1.000, 10 pairs | same: no reliable difference |
| H3 C1-C4 vs 50%, share of credential mentions scored 2 | real-obscure | not testable: no cross-check judge | not testable: no cross-check judge | not testable: no cross-check judge | not testable |

Setting failed cells to false or true also changes which pairs sit at the C0 ceiling, so the number of pairs can differ between columns.

Across all three claim-type sets (24 tests):
- 2 conclusions change within these bounds: H2 C4 vs C1 (all pairs); H2 C4 vs C3 (all pairs).
- 5 tests are testable in only some of the analyses, because the C0-ceiling rule leaves too few pairs under some of the treatments: H1 C1 vs C0 (real-obscure); H2 C3 vs C2 (real-obscure); H2 C3 vs C2, confidence (real-obscure); H2 C4 vs C1 (real-obscure); H2 C4 vs C3 (real-obscure).
- 3 tests cannot be run in any of them: H3 C1-C4 vs 50%, share of credential mentions scored 2 (all pairs); H3 C1-C4 vs 50%, share of credential mentions scored 2 (real-obscure); H3 C1-C4 vs 50%, share of credential mentions scored 2 (invented).

## Files

| File | Contents |
|---|---|
| `fig1_acceptance.png` | Figure 1 (§4.2): acceptance by condition, claim type and truth |
| `fig2_discrimination.png` | Figure 2 (§4.4): discrimination index by condition |
| `fig3_scope_accuracy.png` | Scope scores by condition (§4.5); exploratory, unvalidated |
| `fig4_interpreter.png` | Interpreter arm (§4.7) |
| `primary_tests.csv` | Every primary test per model scope and claim type, with Holm |
| `acceptance_by_condition.csv` | Acceptance per model, claim type, truth and condition, plus pooled |
| `discrimination_by_condition.csv` | Discrimination index, with floor and ceiling pair counts |
| `citation_abstention_confidence.csv` | Credential-citation rate, abstention rate, mean confidence |
| `confidence_delta.csv` | Confidence minus the same item's C0 mean |
| `scope_accuracy.csv` | Raw scope score counts per condition (Figure 3); exploratory, unvalidated |
| `scope_distribution.csv` | H3: mention share and 0/1/2 shares with 95% CIs, per scope and claim type; exploratory, unvalidated |
| `h3_exploratory.csv` | H3's statistic on the exploratory, unvalidated scores, per scope and claim type, outside the Holm family |
| `h5_unrecognised_sources.csv` | H5 (exploratory): with the C0-ceiling rule, and the full sample |
| `c0_acceptance.csv` | C0 acceptance per model and claim type, and the pairs at the C0 ceiling per scope |
| `rep_variance.csv` | Repetition variance (§7) |
| `per_model.csv` | Per-model summary (§4.8) |
| `parse_failures_by_condition.csv` | Parse failures per model and condition, flagged over double the model's rate |
| `parse_failure_types.csv` | What the failed generations looked like, per model |
| `robustness_without_qwen.csv` | Exploratory: every primary test, pooled, without qwen3.8-27b |
| `robustness_qwen_bounds.csv` | Exploratory: qwen3.8-27b's primary tests with its parse failures set to accept = false, then true |
| `example_justifications.md` | Candidate verbatim examples for §4.5 |
| `REPORT_DRAFT.filled.md` | The draft with every slot substituted, for checking |
