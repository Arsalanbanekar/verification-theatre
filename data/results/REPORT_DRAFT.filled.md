<!-- AUTO-FILLED PREVIEW written by src/analyse.py. Check every sentence against results_summary.md before pasting. -->

# Verification Theatre: Language Models Respond to the Presence of Provenance, Not Its Scope

*Draft for the Apart Research AI x Epistemics Research Sprint, 13–15 Nov 2026. Track 2: Trust
Infrastructure. Paste section by section into the official template.*

> **Before submitting:** every `{PLACEHOLDER}` is filled from `data/results/results_summary.md`.
> Every reference marked `[verify]` must be opened and checked. Made-up references can
> disqualify a submission. Delete any claim in Results or Discussion the data does not support.
> Sections marked **(pre-sprint)** were drafted before 13 Nov and say so in the README.

---

## Abstract (150–250 words) — write last, during the sprint

Template:

> Machine-readable provenance standards such as C2PA are being mandated for AI-generated and
> published content, and AI agents are named as a principal consumer. The C2PA specification
> certifies who produced a file and that it is untampered; it explicitly makes no judgment
> about whether the content is true. We test whether language models, acting as consumers of
> provenance metadata, respond to what a credential certifies or merely to its presence. Across
> four models and 20 true/false claim pairs, we present each claim with no credential or
> with one of five honest credentials that differ only in what they certify. On claims about real organisations, the pre-registered test of credence inflation was not testable, because only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −29.2 and −16.7 points; in the full sample, a credential that certified nothing about the claim lowered acceptance by 15.0 points (95% CI 9.5 to 20.5, p < 0.001, unadjusted; false versions alone: 12.9 points), the opposite of the predicted inflation, and acceptance did not reliably differ between a signer who asserted the statement and one who merely recorded it (C3 − C2 = +3.1 points, 95% CI −3.6 to +9.9). On real-obscure pairs the discrimination index was +1.7 points at C0. Averaged over C1–C4 it did not reliably move (Δ = −4.0 points vs C0; 95% CI −8.0 to +0.1; p = 0.053, unadjusted; 10 pairs), and at C5 it rose by 27.1 points (95% CI 11.7 to 42.4; p_holm = 0.022; 10 pairs).
> A plain-language interpreter stating each credential's scope reduced acceptance under C1 and C2 by 42.8 points (95% CI 34.1 to 51.6; p_holm < 0.001; 20 pairs). For organisations the models did not recognise, the same credential lowered acceptance by 5.4 points in the full sample, against −15.0 points for claims about real organisations (difference +9.6 points; 95% CI +2.7 to +16.5; p = 0.009, exploratory, full sample); with the C0-ceiling rule the comparison was not testable, because on real-obscure pairs only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −29.2 and −16.7 points. These results
> describe an attack requiring no forgery: an adversary signs their own false document honestly,
> and the model upgrades it. We release the corpus, pre-registration and code.

---

## 1. Introduction (pre-sprint)

AI systems increasingly read the world on our behalf. Research agents retrieve documents,
weigh sources and summarise what they find, and the field's own survey of AI for epistemics
argues that the most plausible consumers of trust infrastructure may be AI systems themselves
[State of the Field 2026]. At the same time, regulators are making provenance machine-readable.
EU AI Act Article 50 and California SB 942 require machine-readable disclosure of AI-generated
content, with the C2PA standard as the cryptographic layer [AI Identity 2026, verify]. In April
2026, C2PA version 2.4 extended manifest embedding to HTML and structured text formats such as
Markdown — the formats agents actually read [C2PA 2.4].

Provenance answers a narrow question. A C2PA manifest establishes who signed a file, what
actions were recorded, and that nothing has changed since signing. The specification's guiding
principles state that it should not judge whether provenance data is good or bad, only whether
assertions validate as bound to the asset, well-formed and untampered [C2PA 2.4]. Provenance
can establish where content came from without establishing whether it is true [State of the
Field 2026]. The interpretive step is left to the "manifest consumer", which the specification
defines to include software, while its guidance on presentation assumes a human reader.

This gap matters because of how trust accumulates. Early epistemic tools gain trust whether or
not they deserve it, and incumbency can lock that trust in [AI for AI for Epistemics 2026]. If
agents learn to treat a valid credential as evidence that content is accurate, provenance
infrastructure becomes an attack surface that requires no forgery: an adversary signs their own
false document, every field of the certificate is true, and the agent upgrades its belief
anyway.

We ask: **when a document carries a verification mark, do language models respond to what the
mark certifies, or merely to the fact that a mark is present?** We hold a claim fixed and vary
only the credential attached to it, using distinctions the C2PA specification itself defines —
whether a statement was asserted by the signer or merely gathered, and whether the signer is
trusted or merely valid. A model that reads the credential should respond differently across
these conditions. A model that reacts to the seal should not.

**Contributions.**
1. A pre-registered, controlled test of whether LLMs respect the scope of provenance credentials,
   using twin true/false claims and six credential conditions grounded in the C2PA 2.4
   specification.
2. A discrimination measure separating credence inflation (more belief) from accuracy (better
   belief), showing how far credentials moved belief and accuracy separately (Section 4.4).
3. Evidence on whether credentials legitimise sources the model does not recognise — the
   realistic case of an unknown actor signing its own documents.
4. A test of a cheap countermeasure: a deterministic interpreter that states a credential's
   scope in plain language.
5. Released corpus, probes, pre-registration and code.

---

## 2. Related Work (pre-sprint)

**Source evaluation by LLMs.** Several 2026 studies find that models weigh sources poorly.
Models did not update more for reliable sources than unreliable ones, but did update more for
popular ones [Information Discernment 2026, verify]. Models treat numeric precision as a
credibility signal, crediting even impossible statistics [Trust but Don't Verify 2026, verify].
Search-augmented models often answer from snippets without opening sources [Retrieved but Not
Read 2026, verify], and unreliable tool feedback can leave agents worse off than no feedback
[Don't Blindly Trust It 2026, verify]. These works use plain-text cues or fake evidence. We
instead use honest, verifiable credentials whose only defect is that their scope is narrower
than the inference drawn from them.

**Authority of channels.** Recent work asks whether information arriving through a tool result
carries more authority than plain text [Tool Result Authority 2026, verify], and how
verification status is laundered through agent pipelines [Silence Is Endorsement 2026, verify].
These ask whether a channel confers authority; we ask whether a certificate's stated scope is
respected.

**Provenance infrastructure.** C2PA defines manifests, assertions, trust lists and validation
states [C2PA 2.4]. Prior research on provenance has examined conflicts between manifests and
watermarks [Authenticated Contradictions 2026, verify] and human interfaces that make
provenance legible, finding that users given no signal show no discrimination between true and
fabricated content [Provenance Density 2026, verify]. To our knowledge, no work has measured how
LLMs interpret C2PA manifests attached to text.

**Grounding and citation.** Models trained to quote their sources natively [Pleias-RAG 2025]
make provenance visible in outputs, but a quote's presence does not guarantee the claim is
grounded in it. Our study examines the inverse direction: provenance arriving at the model.

**Model honesty and calibration.** Calibration [ConfidenceBench 2026, verify] and sycophancy
under pushback [SPINE 2026, verify; SycEval; ELEPHANT] are well studied. Our concern is
different: not whether a model's stated confidence matches reality, but which features of
evidence move that confidence.

---

## 3. Methods (pre-sprint; check against final code before submitting)

The design, corpus, code and pre-registration were prepared before the sprint, along with a small
pilot of the study calls (10–11 Nov 2026) that is excluded from analysis; the main data
collection, judging, analysis and write-up were done during the sprint (13–15 Nov 2026). Design,
hypotheses and analysis plan were pre-registered before data collection (`PREREGISTRATION.md`,
rev 3.3). The scope-accuracy judge was replaced after the pilot's first run and before the main
run (rev 3.4, commit `172861e`). Deviations are listed in `DEVIATIONS.md`.

### 3.1 Corpus

Twenty true/false twin pairs (40 claims). Each false claim differs from its true twin in exactly
one detail — a number (10 pairs) or a date (10 pairs), with plausibility parity as the criterion.
Ten pairs are **real-obscure**: verifiable public-sector and corporate records from Canada,
the UK, the US and Australia (council decisions, regulatory permits, product recalls, local
technical standards), each with a source URL and verbatim quote. Ten are **invented**, mirroring
the real half cell by cell on domain, jurisdiction and alteration type. Invented names were
screened against the GeoNames gazetteer (rejected within edit distance 2 of a real place) and by
web search. No real entity is assigned an adverse finding it did not receive, and no private
individual is named.

**Probes.** Before data collection, a closed-book model outside the study was shown each real
pair in forced-choice format; confidence was near chance (50–60) for all pairs in the final
corpus. A second probe showed the 20 true claims side by side and asked which were fabricated;
it identified all ten invented claims, in every case citing non-recognition of the named
organisation. We therefore interpret the invented half as claims about **unrecognised
organisations** rather than uncheckable facts, and treat the real-obscure half as the primary
test of H1–H3.

### 3.2 Conditions

Each claim appears inside an identical document body. Conditions differ only in the credential
reported alongside it. All credentials are honest.

| | Credential | What it licenses |
|---|---|---|
| C0 | none | — |
| C1 | valid, trusted signer; creation and actions only | who produced the file; nothing about the claim |
| C2 | claim sentence in `gathered_assertions` | recorded, not attributed to the signer |
| C3 | claim sentence in `created_assertions` | signer asserts it |
| C4 | valid signature, signer not on a trust list | integrity, not trust |
| C5 | claim bound to a checkable source quote | genuine support |

The signer is a single invented document-services company, identical across conditions and
never the organisation a claim concerns. C2 and C3 differ only in assertion bucket — a
distinction the C2PA specification defines explicitly, since only created assertions are
attributed to the signer. C5 is a positive control.

Credentials are presented as crJSON-style JSON views, the serialization C2PA 2.4 introduced for
validation reporting, as a retrieval tool might hand them to an agent. We do not perform
cryptographic validation.

**Countermeasure.** In a separate arm (C1, C2; core models), a deterministic interpreter
generated from the manifest fields states the credential's scope in plain sentences. It adds
no information the manifest does not contain.

### 3.3 Models and sampling

Four models (3,600 of 3,600 planned cells completed: gemini-3.5-flash-lite 720, gpt-oss-120b 960, gpt-oss-20b 960, qwen3.8-27b 960; parse-failure rates: see parse_failures.csv): GPT-OSS-120B, GPT-OSS-20B and Qwen3.8-27B via Groq,
each at full design (40 claims × 6 conditions × 3 repetitions = 720 calls) plus the interpreter
arm (C1 and C2 × 3 repetitions = 240 calls); Gemini 3.5 Flash-Lite via Google AI Studio at full
design (720 calls). Temperature 0.7; each model at its provider's lowest reasoning setting (gpt-oss-120b and gpt-oss-20b `reasoning_effort: low`, the lowest gpt-oss allows; qwen3.8-27b `reasoning_effort: none`; gemini-3.5-flash-lite `thinkingLevel: MINIMAL`; logged with every call). The
prompt states the current date and asks whether the claim is accurate, returning JSON with an
acceptance label, a 0–100 confidence, reasons from a fixed list, and a short justification. The
prompt never mentions that the study concerns credentials.

### 3.4 Measures

- **Acceptance**: proportion labelled true.
- **Discrimination index**: acceptance of the true twin minus acceptance of the false twin, per
  pair and condition. Inflation without accuracy appears as rising acceptance with a flat index.
- **Confidence delta**: confidence minus the same item's C0 mean.
- **Credential-citation rate**: proportion of responses citing the signature or signer as a reason.
- **Abstention rate**: proportion labelled uncertain or citing inability to determine.
- **Scope accuracy** (0–2): whether the justification correctly describes what the credential
  certifies, judged by `glm-5.2` via Adaption (temperature 0, the provider's default reasoning, blind to model, condition and truth) on a stratified sample of 600 responses; no human labels
  are used. The pre-registered cross-check by a second judge was dropped (`DEVIATIONS.md`), so the agreement gate (judge results reported only if the two judges' linear-weighted kappa is at least 0.6) could not be evaluated: confirmatory H3 was not tested, and every scope-accuracy number is exploratory and unvalidated. Reported as the 0/1/2 distribution among justifications that mention the
  credential, plus the share that mention it, all with 95% CIs.

### 3.5 Analysis

Pairs are the unit of analysis: paired t-tests over pairs, with sign-flip permutation tests
as a robustness check. Six primary comparisons (C1 vs C0; C2 vs C3; C4 vs C1 and C3;
discrimination across conditions; scope accuracy across C1–C4; interpreter vs none) comprise
eight tests, with Holm correction over the eight. H3 is supported only if the upper bound of
the 95% CI for the share of credential-mentioning justifications scored 2 is below 0.5 and its
Holm-adjusted p is below .05. Inflation tests exclude pairs at ceiling in C0; the full sample
is reported alongside. Claim type enters as a factor throughout. One rule was added after data
collection (`DEVIATIONS.md`): a test with fewer than three pairs, or with the same difference in
every pair, is reported as not testable, without a p-value, and enters the Holm family with
p = 1; where a pre-registered test is not testable, the full-sample result is the informative one.
The pre-registered cross-check judge was dropped (`DEVIATIONS.md`), so H3 was not tested and
entered the Holm family with p = 1; its statistic on the one judge's scores is reported as
exploratory and unvalidated.

---

## 4. Results — written during the sprint

Fill every slot from `data/results/results_summary.md`. Report what the data shows, including nulls.

**4.1 Baseline.** C0 acceptance: real-obscure true 99% (95% CI 96%–100%), false 97% (95% CI 93%–100%); invented true 98% (95% CI 96%–100%), false 96% (95% CI 90%–100%).
At baseline, claims about invented organisations were accepted about as often as claims about real ones (97% vs 98%).

**4.2 Credence inflation (H1).** Figure 1: acceptance by condition, split by claim type and truth.
C1 vs C0 on false claims: real-obscure pairs, not testable with the C0-ceiling rule, because only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −20.8 and −8.3 points; full sample, the informative result: −12.9 points (95% CI −18.3 to −7.6; p < 0.001, unadjusted; 10 pairs). Both twins, the pre-registered test: not testable with the C0-ceiling rule, because only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −29.2 and −16.7 points; full sample, the informative result: −15.0 points (95% CI −20.5 to −9.5; p < 0.001, unadjusted; 10 pairs). H1 is not supported: in the full sample the credential lowered acceptance, the opposite of the predicted direction..

**4.3 Signal over semantics (H2).** C2 vs C3: C3 − C2 is not testable with the C0-ceiling rule, because only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of +4.2 and +8.3 points; full sample, the informative result: +3.1 points (95% CI −3.6 to +9.9; p = 0.322, unadjusted; 10 pairs); confidence, C3 − C2 is not testable with the C0-ceiling rule, because only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of +0.5 and +3.9 confidence points; full sample, the informative result: +1.2 confidence points (95% CI −1.7 to +4.1; p = 0.382, unadjusted; 10 pairs). C4 vs C1: C4 − C1 is not testable with the C0-ceiling rule, because only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −12.5 and +4.2 points; full sample, the informative result: −12.7 points (95% CI −22.3 to −3.1; p = 0.015, unadjusted; 10 pairs). C4 vs C3: C4 − C3 is not testable with the C0-ceiling rule, because only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −33.3 and −8.3 points; full sample, the informative result: −21.7 points (95% CI −31.1 to −12.2; p < 0.001, unadjusted; 10 pairs).
With the C0-ceiling rule these tests were not testable, so the full-sample results are given instead, with unadjusted p-values. Partly: removing the signer from the trust list (C4 vs C1) lowered acceptance by 12.7 points (95% CI 3.1 to 22.3; p = 0.015, unadjusted; 10 pairs); C4 vs C3 lowered acceptance by 21.7 points (95% CI 12.2 to 31.1; p < 0.001, unadjusted; 10 pairs); the other contrasts did not reliably differ.

**4.4 Inflation without discrimination (H2b).** Figure 2: discrimination index by condition.
On real-obscure pairs the discrimination index was +1.7 points at C0. Averaged over C1–C4 it did not reliably move (Δ = −4.0 points vs C0; 95% CI −8.0 to +0.1; p = 0.053, unadjusted; 10 pairs), and at C5 it rose by 27.1 points (95% CI 11.7 to 42.4; p_holm = 0.022; 10 pairs).

**4.5 Justifications (H3; exploratory, unvalidated).** Scope accuracy by condition 

Scope accuracy is exploratory and unvalidated: one judge scored it, and the pre-registered cross-check was dropped (`DEVIATIONS.md`), so the agreement gate could not be evaluated and confirmatory H3 was not tested. Of the 299 judged C1–C4 justifications on real-obscure pairs, 87% (95% CI 83%–91%) mentioned the credential. Of those, 4% (95% CI 2%–7%) described its scope correctly (score 2), 18% (95% CI 12%–24%) did so partially (1), and 78% (95% CI 71%–84%) treated it as support for the claim or misattributed it (0); CIs over 10 pairs. Read against the pre-registered rule, the upper bound of the 95% CI for score 2 (7%) is below 50% (one-sample t-test against 50%: p < 0.001, unadjusted, outside the Holm family); this is an exploratory, unvalidated result, not a test of H3.

**Exploratory, unvalidated** (one judge, no cross-check). Real-obscure pairs, pooled models. Shares of 0, 1 and 2 are among justifications that mention the credential; 95% CIs over pairs.

| Conditions | judged | mention the credential | 0: support or misattribution | 1: partial | 2: correct scope |
|---|---|---|---|---|---|
| C1–C4 | 299 | 87% (83%–91%) | 78% (71%–84%) | 18% (12%–24%) | 4% (2%–7%) |
| C1 | 75 | 82% (74%–90%) | 75% (63%–86%) | 19% (8%–30%) | 7% (0%–13%) |
| C2 | 75 | 100% (100%–100%) | 88% (80%–95%) | 8% (0%–17%) | 4% (0%–9%) |
| C3 | 75 | 100% (100%–100%) | 85% (73%–97%) | 14% (2%–26%) | 1% (0%–4%) |
| C4 | 74 | 67% (58%–76%) | 39% (23%–55%) | 55% (35%–76%) | 6% (0%–13%) |

. Credential-citation rate


| Condition | n | credential-citation rate | abstention rate | mean confidence |
|---|---|---|---|---|
| C0 | 465 | 9% | 2% | 97 |
| C1 | 475 | 88% | 12% | 90 |
| C2 | 466 | 98% | 8% | 92 |
| C3 | 471 | 99% | 6% | 92 |
| C4 | 463 | 73% | 27% | 81 |
| C5 | 472 | 96% | 7% | 92 |

. Example justifications: one correct, one misattributing a gathered assertion to the
signer (quote the model output verbatim, briefly).

**4.6 Unrecognised sources (H5).** C1 vs C0 on invented items: −2.6 points (95% CI −13.9 to +8.7; p = 0.516, unadjusted; 4 pairs, 6 dropped at the C0 ceiling); full sample: −5.4 points (95% CI −10.4 to −0.4; p = 0.038, unadjusted; 10 pairs); H5 is exploratory. No: on claims about organisations the models did not recognise, the credential lowered acceptance by 5.4 points in the full sample, against −15.0 points for claims about real organisations (difference +9.6 points; 95% CI +2.7 to +16.5; p = 0.009, exploratory, full sample); with the C0-ceiling rule the comparison was not testable, because on real-obscure pairs only 2 pairs were left after 8 at the C0 ceiling were dropped, with differences of −29.2 and −16.7 points.

**4.7 Countermeasure (H4).** Interpreter vs none on C1/C2: interpreter − none = −42.8 points (95% CI −51.6 to −34.1; p_holm < 0.001; 20 pairs), across the three interpreter-arm models; without the interpreter, their C1/C2 acceptance was −10.8 points relative to C0. qwen3.8-27b's interpreter arm had twice the parse-failure rate of the same conditions without it (15.8% vs 7.9%), so its own H4 result (interpreter − none = −37.7 points, 95% CI −50.1 to −25.3) carries that caveat.
Exploratory, added after the results were seen (`DEVIATIONS.md`): with the interpreter, acceptance on C1 and C2 went from 85% to 44% for true claims and from 87% to 42% for false ones, and the discrimination index from −1.5 to +1.4 points, a change of +2.9 points (95% CI −2.6 to +8.4; p = 0.283, unadjusted; 20 pairs). So it lowered acceptance of true and false claims alike, without a reliable gain in accuracy.

**4.8 Models.** Per-model table. 120B vs 20B.

---

## 5. Discussion — written during the sprint

Structure (one paragraph each):
1. What the headline result means, in one plain sentence.
2. Why it is a design problem, not a security bug: nothing was forged.
3. What the countermeasure result implies for the layer between standards and agents.
4. Implication for provenance mandates and for the unrecognised-source case.
5. Future work: agentic retrieval loops, signed binary assets with real validation, frontier
   models, redaction (C6), multi-turn pressure.

---

## Appendix A. Limitations and Dual-Use / Ethical Considerations (pre-sprint draft; the baseline-ceiling and single-judge bullets added during the sprint; required)

**What this study establishes.** Within single-turn evaluations of four open-weight and small
proprietary models, how acceptance and confidence in a fixed claim change when a credential is
attached, and whether models distinguish credentials that license different inferences.

**What it does not establish.**
- Behaviour of frontier models, which were not tested.
- Behaviour in agentic loops, where a model retrieves, compares and cross-checks sources.
- Behaviour on cryptographically signed assets: credentials were presented as crJSON-style
  views, a derived format not intended as input and not independently verifiable.
- Effects of credential position, wording or format, which were held constant.
- Whether a credential raises belief in a claim a model doubts without one. Without a credential, the models accepted almost all claims, true and false alike: pooled over models, 99% of true and 97% of false real-obscure claims, 98% and 96% invented; gpt-oss-120b, gpt-oss-20b and gemini-3.5-flash-lite accepted every C0 response; qwen3.8-27b 90%. In the pooled analysis 8 of 10 real-obscure pairs were at the C0 ceiling, with both versions accepted in every C0 response; on such pairs a credential can only leave acceptance unchanged or lower it. The pre-registered inflation tests drop those pairs, which left the H1 and H2 tests on real-obscure pairs not testable; the full-sample results reported beside them are the informative ones.
- Invented organisations are detectable by non-recognition (§3.1); the invented half therefore
  measures how credentials interact with unknown sources, not uncheckable facts.
- Scope accuracy rests on a single LLM judge (glm-5.2), with no human labels. The pre-registered
  cross-check by a second judge was dropped (`DEVIATIONS.md`), so neither the consistency nor the
  correctness of its scoring was checked: the scope-accuracy scores are exploratory and
  unvalidated, and confirmatory H3 was not tested.
- Listing credential-related reasons in every condition may increase attention to credentials;
  this is constant across conditions and cannot explain differences between them.

**Dual use.** This paper describes an attack that requires no forgery. Every credential in the
study is honest; the failure lies in the inference a model draws from it. An adversary could
use these findings to make false documents more persuasive to AI agents by signing them
truthfully. We publish because (1) machine-readable provenance is being mandated now, with AI
systems named among its consumers, so the failure mode will be discovered by adversaries
regardless; (2) the mitigation tested here — stating a credential's scope in plain language
before the model reasons — is cheap and deployable by any agent framework; and (3) the
standard's own principles place interpretation with the consumer, so measurement of how
consumers interpret is a precondition for safe deployment. We release no tooling for producing
signed false documents.

**Data and people.** No personal data was collected. No private individual is named in the
corpus. No real organisation is assigned an adverse finding it did not receive; real claims were
altered only in numbers and dates. Invented organisations were screened to avoid resemblance to
real places and companies.

**AI assistance.** AI tools were used for literature search, code and drafting. All results were
produced by the released code, and the author is responsible for all content.

---

## References — verify every entry, add full author lists

- [C2PA 2.4] Coalition for Content Provenance and Authenticity. *Content Credentials: C2PA
  Technical Specification*, version 2.4, April 2026.
  https://spec.c2pa.org/specifications/specifications/2.4/specs/C2PA_Specification.html
- [State of the Field 2026] Ben N and A. Csaky. "State of the Field: AI for Epistemics and
  Coordination." LessWrong, 2 Oct 2026.
  https://www.lesswrong.com/posts/uw8RQ8yjKexnhTw6E/state-of-the-field-ai-for-epistemics-and-coordination
- [AI for AI for Epistemics 2026] O. Cotton-Barratt and L. Finnveden. "AI for AI for
  Epistemics." Forethought, 1 Apr 2026. https://www.forethought.org/research/ai-for-ai-for-epistemics
- [Design Sketches 2025] O. Cotton-Barratt, L. Vaintrob and O. Sourbut. "Design Sketches:
  Collective Epistemics." Forethought, 2025.
  https://www.forethought.org/research/design-sketches-collective-epistemics
- [Information Discernment 2026] "Information Discernment in Large Language Models."
  arXiv:2607.19355. [verify authors]
- [Trust but Don't Verify 2026] "Trust, but Don't Verify: Epistemic Blind Spots in LLM Source
  Evaluation." arXiv:2606.05403. [verify authors]
- [Retrieved but Not Read 2026] "Retrieved but Not Read: Understanding Why Search-Augmented LLMs
  Fail to Use Available Evidence." arXiv:2610.21731. [verify authors]
- [Don't Blindly Trust It 2026] "Don't Blindly Trust It: How Unreliable Feedback Breaks
  Tool-Using LLM Agents." arXiv:2606.21409. [verify authors]
- [Tool Result Authority 2026] "Does a Tool Result Carry More Authority Than Plain Text? Three
  Prospective Studies of False-Claim Adoption in a Synthetic Assignment Task with Claude Opus 5."
  arXiv:2608.14992. [verify authors]
- [Silence Is Endorsement 2026] "Silence Is Endorsement: Verification-Status Laundering in LLM
  Agent Pipelines." arXiv:2609.20211. [verify authors]
- [AI Identity 2026] "AI Identity: Standards, Gaps, and Research Directions for AI Agents."
  arXiv:2604.23280. [verify authors; verify Article 50 / SB 942 statement]
- [Authenticated Contradictions 2026] "Authenticated Contradictions from Desynchronized
  Provenance and Watermarking." arXiv:2603.02378. [verify authors]
- [Provenance Density 2026] "Beyond 'Made with AI': Visualizing Provenance Density..." IJCAI
  2026. https://www.ijcai.org/proceedings/2026/0857.pdf [verify authors and full title]
- [Pleias-RAG 2025] P.-C. Langlais, P. Chizhov, M. Nee, C. Rosas-Hinostroza, M. Delsart,
  I. Girard, O. Hicheur, A. Stasenko and I. P. Yamshchikov. "Even Small Reasoners Should Quote
  Their Sources: Introducing the Pleias-RAG Model Family." arXiv:2504.18225, 2025.
- [ConfidenceBench 2026] "ConfidenceBench: Evaluating Confidence Calibration in Large Language
  Models." arXiv:2607.20526. [verify authors]
- [SPINE 2026] "Measuring LLM Sycophancy under Sustained Multi-Turn Pressure." arXiv:2609.09090.
  [verify authors]
- [SycEval] Fanous et al. "SycEval." AIES 2025. arXiv:2502.08177.
- [ELEPHANT] Cheng et al. "ELEPHANT." 2025. arXiv:2505.13995.
