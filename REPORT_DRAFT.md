# Verification Theatre? File-Level Provenance Credentials Change How Much Some Language Models Believe, Not How Well

*Draft for the Apart Research AI x Epistemics Research Sprint, 13–15 Nov 2026. Track 2: Trust
Infrastructure. Paste section by section into the official template.*

> **Status (16 Nov 2026).** Every number below was checked against `data/results/results_summary.md`
> and the results CSVs (analysis at commit `36898c0`), including which claims and models it covers.
> Every reference was checked: the ones that needed it were opened, their titles confirmed and
> their authors filled in. Figures are in `data/results/` (`fig1_acceptance.png` to
> `fig4_interpreter.png`). Sections marked **(pre-sprint)** were drafted before 13 Nov and say so in
> the README.

---

## Abstract

Machine-readable provenance is being mandated for published and AI-generated content, and since
version 2.4 the C2PA standard can embed credentials in the text formats AI agents read. A C2PA
credential certifies who signed content and that it is untampered; the specification makes no
judgment about whether the content is true. We pre-registered a test of whether language models
respond to what a credential certifies or merely to its presence. Four models judged 20
true/false claim pairs presented with no credential or with one of five honest credentials that
differ only in what they certify (3,600 trials, including a countermeasure arm). Without a
credential, models accepted nearly every claim, true or false. Contrary to our hypothesis, a
credential that certified nothing about the claim lowered acceptance of real-world claims (−15.0
percentage points, 95% CI −20.5 to −9.5). We found no reliable difference
between a signer who asserted a statement and one who merely recorded it (+3.1, CI −3.6 to 9.9);
an untrusted signer lowered acceptance (−12.7), mainly in one model. Credentials changed how much
models believed, not how well: true–false discrimination stayed flat until a credential bound the
claim to a checkable source (+27.1, reliable in one model). In exploratory scoring by a single
unvalidated judge, about 4% of justifications mentioning a credential described its scope
correctly. In three models, a plain-language summary of each credential's scope lowered
acceptance by a further 42.8 points without a reliable gain in discrimination. We release the
corpus, pre-registration, code and data.

---

## 1. Introduction (drafted pre-sprint; condensed during the sprint, when the Contributions and the two sentences before them were written)

AI agents increasingly read documents on our behalf, and a recent survey argues that the most
plausible consumers of trust infrastructure may be AI systems themselves [State of the Field 2026].
EU AI Act Article 50 and California SB 942 require machine-readable disclosure of AI-generated
content, with the C2PA standard as the cryptographic layer [AI Identity 2026], and since April 2026
C2PA version 2.4 can embed manifests in HTML and Markdown, the formats agents read [C2PA 2.4]. A
manifest establishes who signed a file and that nothing has changed since signing, not whether its
content is true [C2PA 2.4; State of the Field 2026]. Interpreting it is left to the "manifest
consumer", which the specification defines to include software, while its guidance on presentation
assumes a human reader. Early epistemic tools gain trust whether or not they deserve it [AI for AI
for Epistemics 2026], and if agents treat a valid credential as evidence that content is accurate,
provenance becomes an attack surface that needs no forgery: an adversary signs their own false
document honestly, and the agent upgrades its belief.

We ask: **when a document carries a verification mark, do language models respond to what the mark
certifies, or merely to the fact that a mark is present?** We hold a claim fixed and vary only the
credential attached to it, using distinctions the C2PA specification itself defines: whether a
statement was asserted by the signer or merely gathered, and whether the signer is trusted or merely
valid. We predicted that credentials would inflate belief. They did not; what they changed, and what
they failed to change, is the subject of this paper.

**Contributions.**
1. A pre-registered, controlled test of how language models respond to C2PA credentials attached
   to text, using twin true/false claims, no credential and five credentials defined by C2PA 2.4;
   the corpus, probes, pre-registration, code and data are released.
2. Evidence that file-level credentials change how much models believe, not how well. We found no
   credence inflation. Instead, credentials lowered acceptance in two of four models; models
   ignored the attribution distinction the standard defines while, pooled, responding to trust
   status, mainly in one model; and discrimination improved only when a credential bound the claim
   to a checkable source, reliably in one model.
3. Exploratory evidence that models rarely describe a credential's scope correctly.
4. A test of a cheap countermeasure, a plain-language scope summary, which lowered acceptance
   across the board without improving accuracy.

---

## 2. Related Work (drafted pre-sprint; citations checked and the section condensed during the sprint)

**Source evaluation and channels.** Models rely on a source's popularity about twice as much as on
its reliability [Information Discernment 2026] and give statistically impossible confidence
intervals the same weight as valid ones [Trust but Don't Verify 2026]; search-augmented models often
answer from snippets without opening sources [Retrieved but Not Read 2026], and persistently
misleading tool feedback can leave agents worse off than none [Don't Blindly Trust It 2026]. Other
work asks whether a tool result carries more authority than plain text [Tool Result Authority 2026]
and how verification status is laundered through agent pipelines [Silence Is Endorsement 2026].
These works test plain-text cues, fake evidence or channels; we test honest, verifiable credentials
whose only defect is that their scope is narrower than the inference drawn from them.

**Provenance, grounding and calibration.** Provenance research has examined conflicts between
manifests and watermarks [Authenticated Contradictions 2026] and interfaces that make provenance
legible to people, finding that participants given no signal showed no detectable discrimination
between true and fabricated content [Provenance Density 2026]; to our knowledge, no work has
measured how LLMs interpret C2PA manifests attached to text. Models trained to quote their sources
make provenance visible in their outputs [Pleias-RAG 2025]; we study the inverse. Calibration
[ConfidenceBench 2026] and sycophancy [SPINE 2026; SycEval; ELEPHANT] are well studied; our concern
is which features of evidence move a model's confidence.

---

## 3. Methods (drafted pre-sprint; updated and condensed during the sprint)

The design, corpus, code and pre-registration (`PREREGISTRATION.md`, rev 3.3; the judge was replaced
in rev 3.4, before the main run) were prepared before the sprint, with a pilot that is excluded from
all analysis. Data collection (14–15 Nov 2026), judging, analysis and write-up were done during the
sprint, and every change made after data collection began is listed in `DEVIATIONS.md`. Appendix
B.1–B.2 give the methods in full.

**Table 1.** The six conditions: the credential shown with the claim, and what it licenses.

| | Credential | What it licenses |
|---|---|---|
| C0 | none | — |
| C1 | valid, trusted signer; creation and actions only | who produced the file; nothing about the claim |
| C2 | claim sentence in `gathered_assertions` | recorded, not attributed to the signer |
| C3 | claim sentence in `created_assertions` | signer asserts it |
| C4 | valid signature, signer not on a trust list | integrity, not trust |
| C5 | claim bound to a checkable source quote | genuine support |

**Corpus and conditions.** Twenty true/false twin pairs (40 claims): each false twin differs from
its true twin in one number or one date. Ten pairs are **real-obscure** public-sector and corporate
records from Canada, the UK, the US and Australia; ten are **invented**, mirroring them cell by
cell. Probes found the real claims obscure and the invented organisations unrecognised, so we read
the invented half as claims about **unrecognised organisations**, not uncheckable facts, and treat
the real-obscure half as the primary test of H1–H3. Each claim appears in an identical document
body, alone (C0) or with one of five honest credentials, shown as crJSON-style JSON views without
cryptographic validation (Table 1). The signer, an invented document-services company, is the same
in every condition and never the organisation a claim concerns. C2 and C3 differ only in assertion
bucket, a distinction the C2PA specification defines; C5 is a positive control. In a countermeasure
arm (C1 and C2, three models), a deterministic interpreter states each credential's scope in plain
sentences.

**Models and measures.** GPT-OSS-120B, GPT-OSS-20B and Qwen3.8-27B via Groq answered 960 calls each,
240 of them in the interpreter arm, and Gemini 3.5 Flash-Lite via Google AI Studio answered 720: all
3,600 planned calls, three repetitions per cell, at temperature 0.7 and each provider's lowest
reasoning setting. The prompt, which never mentions that the study concerns credentials, asks for
JSON with a verdict, a 0–100 confidence, reasons from a fixed list and a short justification; 106 of
Qwen's responses (11.0%) failed to parse twice and are missing data. **Acceptance** is the share
labelled true. The **discrimination index** is true-twin minus false-twin acceptance per pair, so
inflation without accuracy appears as rising acceptance with a flat index. **Scope accuracy** scores
whether a justification correctly describes what the credential certifies and that it does not bear
on the claim's truth (2), does so partially (1), or treats it as support for the claim or
misattributes it (0). One judge, `glm-5.2` via Adaption, blind to model, condition and truth, scored
a stratified sample of 600 C1–C4 responses; the pre-registered second judge was dropped, so every
scope-accuracy number is exploratory and unvalidated.

**Analysis.** Pairs are the unit of analysis, compared with paired t-tests and Holm correction over
the eight tests of the six primary comparisons. Inflation tests exclude pairs at ceiling in C0, and
full-sample results are reported alongside with unadjusted p-values. A test with fewer than three
pairs or no variation is not testable and enters the Holm family with p = 1 (a rule added after data
collection), as does H3, which was not tested. H5 and analyses added after the data were seen are
exploratory.

---

## 4. Results (written during the sprint; condensed for the template)

**Baseline.** Without a credential (C0), gpt-oss-120b, gpt-oss-20b and Gemini 3.5 Flash-Lite
accepted every claim, and Qwen3.8-27B accepted 90% (92% of real-obscure and 88% of invented claims),
true and false twins alike: baseline discrimination was near zero (+1.7 points on real-obscure
pairs). Excluding pairs at ceiling left 2 of the 10 real-obscure pairs, too few for a test, so every
pre-registered H1 and H2 test is reported as not testable; below are the full-sample results the
pre-registration specified alongside, with unadjusted p-values. Table 2 (Appendix B.3) gives the
main results per model.

**Credentials lowered acceptance (H1).** H1 is not supported, and the effect runs the other way. A
valid credential that certified nothing about the claim (C1) lowered acceptance of real-obscure
claims by 15.0 points (95% CI 9.5 to 20.5; p < .001, unadjusted; Figure 1); on the false twins alone
the drop was 12.9 points (95% CI 7.6 to 18.3; p < .001, unadjusted). The drop was concentrated in
two models (Table 2). gpt-oss-20b (−28.3, p = .008) and Qwen (−26.7, p = .008) became markedly more
cautious; Gemini barely moved (−5.0, p = .34); and gpt-oss-120b did not move at all (0.0 in every
pair). These per-model p-values are unadjusted. For claims about invented organisations (H5,
exploratory; Appendix B.5), credentials lowered acceptance too, by less than for real claims.

*Figure 1. Acceptance by condition, split by claim type and truth, pooled over models (95% CIs over
claims; `data/results/fig1_acceptance.png`).*

**Trust status, not attribution (H2).** Models did not reliably distinguish a signer who asserted
the claim (C3, `created_assertions`) from one who merely recorded it (C2, `gathered_assertions`):
+3.1 points (95% CI −3.6 to 9.9, p = .32, unadjusted). The interval rules out a C3 advantage larger
than about 10 points and a C2 advantage larger than about 4. Pooled over models, acceptance did
respond to whether the signer was trusted. A valid signature from a signer absent from any trust
list (C4) lowered acceptance relative to C1 (−12.7, CI −22.3 to −3.1, p = .015) and relative to C3
(−21.7, CI −31.1 to −12.2, p < .001; both unadjusted). The C4 effect came mainly from Qwen (−42.5
relative to C1, p = .010, unadjusted; Table 2). Two of Qwen's own C4 tests also change conclusion
within the bounds of its parse failures (Appendix B.6). Models read whether the signer was trusted,
but not what the signer vouched for.

**Belief changed, discrimination did not (H2b).** Across C1–C4, the gap between acceptance of true
and false twins did not improve on C0 (−4.0 points, 95% CI −8.0 to 0.1, p = .053, unadjusted). It
rose only under C5, where the credential tied the claim to a checkable source quote: +27.1 points
over C0 (95% CI 11.7 to 42.4, p_holm = .022; Figure 2). The discrimination pattern H2b predicted
therefore held, flat through C4 and rising at C5, though alongside falling rather than rising
acceptance. The positive control behaved as designed, but reliably in one model only. Gemini's
discrimination rose by 90.0 points at C5 (p_holm < .001). The three Groq models' gains (+1.7 to
+10.0) were not reliable (Table 2).

**Justifications (exploratory; H3 not tested).** What follows rests on a single, unvalidated judge
(glm-5.2). Of 299 judged real-obscure justifications, 87% (95% CI 83–91%) mentioned the credential;
of those, 78% (71–84%) treated it as support for the claim or misattributed it (score 0), 18%
(12–24%) described its scope partially (score 1), and 4% (2–7%) described it correctly (score 2).
Neither gpt-oss model produced a fully correct description in any pair. Among their
credential-mentioning justifications, Qwen did so in 15% and Gemini in 2% (pair-level means; Table
2). Misreadings were most frequent for gathered assertions: under C2, 88% scored 0 (Figure 3,
Appendix B.7). Under C4, 55% of mentions described the credential partially (score 1), against 8–19%
under C1–C3, and fewer justifications mentioned the credential at all (67%). gpt-oss-120b's
acceptance was unmoved by credentials, yet in exploratory scoring it never described their scope
fully correctly: stable behaviour is not the same as correct reading. Two verbatim examples are in
Appendix B.4.

*Figure 2. Discrimination index (true-twin minus false-twin acceptance) by condition and claim type,
pooled over models (95% CIs over pairs; `data/results/fig2_discrimination.png`).*

**The scope interpreter (H4).** Prepending a plain-language summary of what each credential
certifies lowered acceptance on C1 and C2 by 42.8 points (95% CI 34.1 to 51.6, p_holm < .001; three
Groq models, all 20 pairs; Figure 4, Appendix B.7). It did so indiscriminately: acceptance of true
claims fell from 85% to 44% and of false claims from 87% to 42%; the change in discrimination was
+2.9 points (CI −2.6 to 8.4, p = .28, unadjusted, exploratory); and no single model showed a
reliable gain. Qwen's interpreter arm had twice the parse-failure rate of the same conditions
without it (15.8% vs 7.9%), so its own H4 estimate carries that caveat; Appendix B.6 reports Qwen's
parse failures and the exploratory robustness checks.

---

## 5. Discussion (written during the sprint; condensed for the template)

**Credentials did not make models more credulous.** The attack we set out to measure, an honest
signature raising belief in a false document, did not appear in these four models. The vulnerability
sat in the baseline: with no credential at all, three of the four models accepted every claim a
document stated, false ones included, and the fourth accepted 90%. A credential cannot inflate
belief already at ceiling; in our setting the threat to accuracy came from credulity towards
documents, not from credentials.

**But credentials moved belief without informing it.** Pooled over models, acceptance shifted with
trust status, a property of the signer, though mainly in one model. In none did it shift reliably
with whether the signer asserted the claim, which is the distinction the C2PA specification uses to
define responsibility. Discrimination between true and false claims did not reliably change in any
model across the four credentials that bore no relation to the claim's truth, and when models
explained themselves, they rarely described what a credential covered (exploratory). File-level
credentials changed how much some models believed, and in none of them how well: a form of
verification theatre in which a seal shifts confidence while the statement inside it goes unread.

**Telling models what a credential covers made them doubt true and false claims alike.** The
interpreter adds no information the manifest lacks. In each of the three models tested, it lowered
acceptance of true and false claims almost equally, trading credulity for indiscriminate scepticism.
The missing layer between provenance standards and their machine consumers is therefore not
presentation alone. The one condition that improved accuracy was C5, where the credential connected
the claim to a checkable source, though reliably so only in Gemini. A model can use provenance when
it bears on the claim; the models we tested did not, on their own, infer what a file-level
credential does and does not establish.

**Implications for provenance mandates.** Our results suggest that file-level credentials, which
certify signers and integrity, will not by themselves make agents more accurate, and may shift
belief in ways unrelated to truth: in our data an untrusted signer lowered acceptance of true claims
as well as false ones, mainly in one model. Claim-level binding, where a credential ties a statement
to its evidence, is the design that helped, though in our data reliably only for Gemini. For agent
developers, the practical lesson is to evaluate provenance consumption by discrimination, not
acceptance: a pipeline that becomes more cautious is not thereby more correct.

**Measured against an epistemic code.** Navaie's ECAISA, an Epistemic Code for AI Safety and
Alignment, asks that safety-relevant claims leave an auditable record, inspectable and contestable
by independent reviewers: transparent evidence, claims proportionate to that evidence, independent
and adversarial attempts to break them, and warranted claims kept apart from tidy narrative [Navaie
2026]. This study meets most of these: its pre-registration was pushed to the public repository
before data collection, every later change is in a timestamped deviations log, the corpus, code and
data are released, and unadjusted, exploratory and per-model results are labelled as such. It does
not meet independent verification: the scope-accuracy judge is a single unvalidated model, and no
result has been replicated. Independent verification is therefore the priority for follow-up work:
replication of these results, and validation of the scope judge by a second judge or human raters.

**Future work.** Our documents asserted their own claims, which produced the baseline ceiling;
future designs should vary document reliability so that inflation is measurable. Agentic retrieval
with competing sources, cryptographically signed assets with real validation, frontier models,
higher reasoning settings and the redaction condition (C6) are natural extensions.

---

## 6. Conclusion (written during the sprint)

File-level provenance credentials changed how much some language models believed, not how well.
Pooled over models, acceptance responded to a signer's trust status, mainly in one model, but not
reliably to whether the signer asserted the claim, and only a credential that bound the claim to a
checkable source improved discrimination, reliably in one model. In the three models tested, a
plain-language summary of each credential's scope produced indiscriminate doubt, lowering acceptance
of true and false claims alike. Provenance consumption by AI systems should therefore be evaluated
by discrimination, not acceptance.

---

## Appendix A. Limitations and Dual-Use / Ethical Considerations (pre-sprint draft; the limitations and dual-use text rewritten during the sprint; required)

**What this study establishes.** Within single-turn evaluations of four open-weight and small
proprietary models, how acceptance and confidence in a fixed claim change when a credential is
attached, and whether models distinguish credentials that license different inferences.

**What it does not establish.**
- **Baseline ceiling.** The documents asserted their own claims, and three of four models accepted
  every claim at baseline. The pre-registered inflation tests were therefore not testable, and the
  H1/H2 conclusions rest on full-sample results with unadjusted p-values.
- **Unvalidated judge.** Scope accuracy rests on a single LLM judge (glm-5.2) with no second judge
  or human validation, so it is exploratory. The judge was not deterministic at temperature 0, and
  30 of 600 judgements were re-asked with a higher token cap after hitting the original cap.
- **Parse failures.** Qwen returned invalid JSON in 11% of trials, more often in the interpreter arm.
- **Settings.** All models ran at their lowest reasoning setting; more deliberate settings may read
  credentials differently.
- **Scope.** Four models, single-turn, credentials presented as crJSON-style views rather than
  cryptographically validated signed assets.
- Behaviour of frontier models, which were not tested.
- Behaviour in agentic loops, where a model retrieves, compares and cross-checks sources.
- Effects of credential position, wording or format, which were held constant.
- Invented organisations are detectable by non-recognition (§3); the invented half therefore
  measures how credentials interact with unknown sources, not uncheckable facts.
- Listing credential-related reasons in every condition may increase attention to credentials;
  this is constant across conditions and cannot explain differences between them.

**Dual use.** This study set out to measure an attack requiring no forgery: honest credentials
attached to false documents. We did not find that credentials raised acceptance of false claims in
the models tested. We did find that credentials shifted belief independently of truth; in
particular, a valid signature from an untrusted signer lowered acceptance, which could in principle
be used to cast doubt on genuine content. We publish because machine-readable provenance is being
mandated now, with AI systems among its intended consumers, and because the remedies our results
point to, claim-level binding and evaluating provenance consumption by discrimination rather than
acceptance, are defensive. We release no tooling for producing signed documents, no real
organisation is assigned an adverse finding in the corpus, and no private individual is named.

**Data and people.** No personal data was collected. No private individual is named in the
corpus. No real organisation is assigned an adverse finding it did not receive; real claims were
altered only in numbers and dates. Invented organisations were screened to avoid resemblance to
real places and companies.

**AI assistance.** AI tools were used for literature search, code and drafting. All results were
produced by the released code, and the author is responsible for all content.

---

## Appendix B. Supplementary methods and results

### B.1 Timeline, corpus and conditions

The design, corpus, code and pre-registration were prepared before the sprint, together with a
pilot of the study calls on 10–11 Nov 2026 that is excluded from all analysis; the repository as
it stood then is tagged `pre-sprint`. Main data collection (14–15 Nov 2026, UTC), judging,
analysis and write-up were done during the sprint (13–15 Nov 2026), and every study call used the
prompt-building and model-calling code at that tag. Design, hypotheses and analysis plan were
pre-registered before data collection (`PREREGISTRATION.md`, rev 3.3). The scope-accuracy judge
was replaced after the pilot's first run and before the main run (rev 3.4, commit `172861e`).
Every change made after data collection began is listed with its time and reason in
`DEVIATIONS.md` and noted below where it applies.

Twenty true/false twin pairs (40 claims). Each false claim differs from its true twin in exactly
one detail — a number (10 pairs) or a date (10 pairs), with plausibility parity as the criterion.
Ten pairs are **real-obscure**: verifiable public-sector and corporate records from Canada,
the UK, the US and Australia (council decisions, regulatory permits, product recalls, local
technical standards), each with a source URL and verbatim quote. Ten are **invented**, mirroring
the real half cell by cell on domain, jurisdiction and alteration type. Invented names were
screened against the GeoNames gazetteer (rejected within edit distance 2 of a real place) and by
web search. No real entity is assigned an adverse finding it did not receive, and no private
individual is named.

Before data collection, a closed-book model outside the study was shown each real
pair in forced-choice format; confidence was near chance (50–60) for all pairs in the final
corpus. A second probe showed the 20 true claims side by side and asked which were fabricated;
it identified all ten invented claims, in every case citing non-recognition of the named
organisation.

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

### B.2 Models, measures and analysis

Four models: GPT-OSS-120B, GPT-OSS-20B and Qwen3.8-27B via Groq, each at full design (40 claims ×
6 conditions × 3 repetitions = 720 calls) plus the interpreter arm (40 claims × C1 and C2 × 3
repetitions = 240 calls); Gemini 3.5 Flash-Lite via Google AI Studio at full design (720 calls).
All 3,600 planned calls were completed. Temperature 0.7; each model at its provider's lowest
reasoning setting (gpt-oss `reasoning_effort: low`, the lowest gpt-oss allows; Qwen
`reasoning_effort: none`; Gemini `thinkingLevel: MINIMAL`), logged with every call. The prompt
states the current date and asks whether the claim is accurate, returning JSON with an acceptance
label, a 0–100 confidence, reasons from a fixed list, and a short justification. The prompt never
mentions that the study concerns credentials. A response that failed to parse on both attempts is
missing data and is never imputed: 106 of Qwen's 960 calls (11.0%), and none for the other three
models.

- **Acceptance**: proportion labelled true.
- **Discrimination index**: acceptance of the true twin minus acceptance of the false twin, per
  pair and condition. Inflation without accuracy appears as rising acceptance with a flat index.
- **Scope accuracy** (0–2): whether the justification correctly describes what the credential
  certifies and that it does not bear on the claim's truth (2), does so partially (1), or treats
  the credential as support for the claim or misattributes it (0); justifications that do not
  mention the credential are N/A.
  - One judge scored a sample of 600 C1–C4 responses, stratified by model, condition and claim
    type: `glm-5.2` via Adaption, at temperature 0 with the provider's default reasoning, blind to
    model, condition and truth.
  - Thirty of its 600 replies hit the 4,000-token output cap without a score. Each was re-asked
    once with a 12,000-token cap, and all 600 then had a valid score.
  - The pre-registration specified judges on OpenRouter with a cross-check by a second judge.
    Before any main-data judging, the judge moved to Adaption and the cross-check was dropped
    (`DEVIATIONS.md`). The agreement gate (judge results reported only if the two judges'
    linear-weighted kappa is at least 0.6) therefore could not be evaluated: confirmatory H3 was
    not tested, and every scope-accuracy number is exploratory and unvalidated.
  - We report the 0/1/2 distribution among justifications that mention the credential, plus the
    share that mention it, all with 95% CIs; no human labels are used.
- **Confidence delta**: confidence minus the same item's C0 mean.
- **Credential-citation rate**: proportion of responses citing the signature or signer as a reason.
- **Abstention rate**: proportion labelled uncertain or citing inability to determine.

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
Full-sample results lie outside the Holm family, so their p-values are unadjusted and labelled as
such. The pre-registered cross-check judge was dropped (`DEVIATIONS.md`), so H3 was not tested and
entered the Holm family with p = 1; its statistic on the one judge's scores is reported as
exploratory and unvalidated.

Several analyses are exploratory, and are labelled so wherever they appear. Three were added
after the data were seen: robustness checks for Qwen's parse failures; the discrimination index
with and without the interpreter; and H3's statistic on the single judge's scores. H5 was
pre-registered as exploratory.

### B.3 Per-model results

**Table 2.** Per model, real-obscure pairs.

| Model | C0 acceptance | C1 − C0 | C3 − C2 | C4 − C1 | Discrimination, C5 − C0 | Scored 2 (exploratory) |
|---|---|---|---|---|---|---|
| gpt-oss-120b | 100% | 0.0 | +1.7 | 0.0 | +6.7 | 0% |
| gpt-oss-20b | 100% | −28.3* | +3.3 | +3.3 | +10.0 | 0% |
| Qwen3.8-27B | 92% | −26.7* | +7.5 | −42.5* | +1.7 | 15% |
| Gemini 3.5 Flash-Lite | 100% | −5.0 | 0.0 | −11.7 | +90.0* | 2% |
| Pooled | 98% | −15.0* | +3.1 | −12.7* | +27.1* | 4% |

Notes to Table 2:
- Differences are in percentage points.
- C1 − C0, C3 − C2 and C4 − C1 are full-sample results, because the pre-registered tests were not
  testable at the C0 ceiling.
- Discrimination, C5 − C0, is the pre-registered test, on all 10 pairs.
- "Scored 2" is the share of credential-mentioning justifications scored 2, as a pair-level mean.
  It is exploratory and unvalidated.
- A 0.0 for gpt-oss-120b (C1 − C0, C4 − C1) or Gemini (C3 − C2) is zero in every pair.
- \* marks p < .05: unadjusted for the full-sample columns, Holm-adjusted for C5 − C0.

### B.4 Example justifications

Two verbatim examples:
- **Score 0** (Gemini 3.5 Flash-Lite, C2, accepting the false twin of an invented claim): "The
  document contains a valid cryptographic C2PA manifest signed by Vellumworth Document Services
  Ltd with all validation checks succeeding, confirming that the statement originates securely
  from the publisher." The statement was only gathered, never attributed to the signer.
- **Score 2** (Gemini 3.5 Flash-Lite, C4, answering "uncertain" to the false twin of an invented
  claim; excerpt): "The document contains a valid cryptographic signature, but the signing certificate is
  marked as untrusted and there is insufficient external evidence to verify the factual
  accuracy …"

### B.5 Unrecognised sources (H5, exploratory)

In the single-document setting, models did not reject claims about invented organisations at
baseline. They accepted them at rates similar to real ones: 98% of true and 96% of false invented
claims, against 99% and 97% of real-obscure ones. This is unlike the side-by-side realness probe (Appendix B.1).

In the full sample, credentials lowered acceptance of invented claims as well (−5.4 points, 95% CI
−10.4 to −0.4, p = .038, unadjusted), but less than for real claims (difference 9.6 points, 95% CI
2.7 to 16.5, p = .009, unadjusted). With the C0-ceiling rule the comparison was not testable.
Credentials did not lend legitimacy to unrecognised sources.

### B.6 Parse failures and robustness checks

Qwen failed to return valid JSON in 106 of 960 trials (11.0%). No condition's rate exceeded twice
Qwen's average (22.1%). Its rates did differ across conditions (χ²(7) = 16.9, p = .018), and were
twice as high with the interpreter on C1 and C2 (15.8% vs 7.9%, Fisher p = .011).

Exploratory robustness checks re-ran the pre-registered tests without Qwen, and with Qwen's failed
cells set first to all-reject and then to all-accept.
- **Without Qwen**, one pooled conclusion changed: discrimination at C5 on invented pairs became
  reliable (+23.3 points, p_holm = .049, against +24.2, p_holm = .115, with Qwen). The pooled
  real-obscure inflation tests cannot be run at all without Qwen, because every remaining pair is at
  the C0 ceiling.
- **Within Qwen's bounds**, two of its own tests changed. Its C4 − C1 and C4 − C3 differences on all
  pairs became reliable decreases when every failed cell counted as a rejection (−28.6 and −32.1
  points; p_holm = .019 and .013).

### B.7 Figures 3 and 4

*Figure 3. Scope-accuracy scores of the judged C1–C4 justifications by condition, pooled over
models and claim types, including justifications that do not mention the credential (exploratory
and unvalidated: one judge; `data/results/fig3_scope_accuracy.png`).*

*Figure 4. Acceptance on C1 and C2 with and without the scope interpreter, per interpreter-arm
model, with each model's C0 acceptance marked (`data/results/fig4_interpreter.png`).*

---

## References

- [C2PA 2.4] Coalition for Content Provenance and Authenticity. *Content Credentials: C2PA
  Technical Specification*, version 2.4, April 2026.
  https://spec.c2pa.org/specifications/specifications/2.4/specs/C2PA_Specification.html
- [State of the Field 2026] Ben N and A. Csaky. "State of the Field: AI for Epistemics and
  Coordination." LessWrong, 2 Oct 2026.
  https://www.lesswrong.com/posts/uw8RQ8yjKexnhTw6E/state-of-the-field-ai-for-epistemics-and-coordination
- [AI for AI for Epistemics 2026] O. Cotton-Barratt and L. Finnveden. "AI for AI for
  Epistemics." Forethought, 1 Apr 2026. https://www.forethought.org/research/ai-for-ai-for-epistemics
- [Information Discernment 2026] J. Ashkinaze, L. Kurek, A. Faisal, T. Miao, M. Joseph, C. Budak
  and E. Gilbert. "Information Discernment in Large Language Models." arXiv:2607.19355, 2026.
  https://arxiv.org/abs/2607.19355
- [Trust but Don't Verify 2026] R. N. Pradhan and S. Goley. "Trust, but Don't Verify: Epistemic
  Blind Spots in LLM Source Evaluation." arXiv:2606.05403, 2026. https://arxiv.org/abs/2606.05403
- [Retrieved but Not Read 2026] O. Walters, L. Chen and F. Toni. "Retrieved but Not Read:
  Understanding Why Search-Augmented LLMs Fail to Use Available Evidence." arXiv:2610.21731, 2026.
  https://arxiv.org/abs/2610.21731
- [Don't Blindly Trust It 2026] C. Zhang, Z. Wan, X. Yu, P. Zhou, W. Zhao, J. Wu, Y. Zhou and
  I. Tsang. "Don't Blindly Trust It: How Unreliable Feedback Breaks Tool-Using LLM Agents."
  arXiv:2606.21409, 2026. https://arxiv.org/abs/2606.21409
- [Tool Result Authority 2026] J. Bronder. "Does a Tool Result Carry More Authority Than Plain
  Text? Three Prospective Studies of False-Claim Adoption in a Synthetic Assignment Task with
  Claude Opus 5." arXiv:2608.14992, 2026. https://arxiv.org/abs/2608.14992
- [Silence Is Endorsement 2026] Y. Hu. "Silence Is Endorsement: Verification-Status Laundering in
  LLM Agent Pipelines." arXiv:2609.20211, 2026. https://arxiv.org/abs/2609.20211
- [AI Identity 2026] T. Otsuka, K. Toyoda and A. Leung. "AI Identity: Standards, Gaps, and
  Research Directions for AI Agents." arXiv:2604.23280, 2026. https://arxiv.org/abs/2604.23280
- [Authenticated Contradictions 2026] A. Nemecek, H. He, G. Cheng and E. Ayday. "Authenticated
  Contradictions from Desynchronized Provenance and Watermarking." CVPR 2026 Workshop on
  Authenticity & Provenance in the Age of AI (APAI). arXiv:2603.02378.
  https://arxiv.org/abs/2603.02378
- [Provenance Density 2026] Q. Zhang, Y. Huang, J. Lee, T. Starner and J. Rekimoto. "Beyond 'Made
  with AI': Visualizing Provenance Density to Mitigate the Transparency Penalty." In *Proceedings
  of the Thirty-Fifth International Joint Conference on Artificial Intelligence (IJCAI 2026)*,
  pp. 7712–7720, 2026. https://doi.org/10.24963/ijcai.2026/857
- [Pleias-RAG 2025] P.-C. Langlais, P. Chizhov, M. Nee, C. Rosas-Hinostroza, M. Delsart,
  I. Girard, O. Hicheur, A. Stasenko and I. P. Yamshchikov. "Even Small Reasoners Should Quote
  Their Sources: Introducing the Pleias-RAG Model Family." arXiv:2504.18225, 2025.
- [ConfidenceBench 2026] M. ffrench-Constant, D. Yang, X. Huang and S. Kapoor. "ConfidenceBench:
  Evaluating Confidence Calibration in Large Language Models." arXiv:2607.20526, 2026.
  https://arxiv.org/abs/2607.20526
- [SPINE 2026] L. Tang, K. Wei, T. Jiang and R. Huang. "SPINE: Measuring LLM Sycophancy under
  Sustained Multi-Turn Pressure." arXiv:2609.09090, 2026. https://arxiv.org/abs/2609.09090
- [SycEval] Fanous et al. "SycEval." AIES 2025. arXiv:2502.08177.
- [ELEPHANT] Cheng et al. "ELEPHANT." 2025. arXiv:2505.13995.
- [Navaie 2026] K. Navaie. "Epistemic norms for AI safety and alignment research." *Artificial
  Intelligence Review* 59(12), article 265, 2026. https://doi.org/10.1007/s10462-026-11666-8
