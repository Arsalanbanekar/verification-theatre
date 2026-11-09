# Verification Theatre: Language Models Respond to the Presence of Provenance, Not Its Scope

*Draft for the Apart Research AI x Epistemics Research Sprint, 13–15 Nov 2026. Track 2: Trust
Infrastructure. Paste section by section into the official template.*

> **Before submitting:** every `{PLACEHOLDER}` is filled from `data/results_summary.md`.
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
> {N_MODELS} models and 20 true/false claim pairs, we present each claim with no credential or
> with one of five honest credentials that differ only in what they certify. {HEADLINE RESULT:
> one sentence, e.g. "A credential that certified nothing about the claim raised acceptance of
> false claims by X points (CI), and models did not distinguish a signer who vouched for a
> statement from one who merely recorded it."} {DISCRIMINATION RESULT: one sentence on whether
> credentials raised acceptance without improving the ability to tell true from false.}
> {INTERPRETER RESULT: one sentence.} {UNRECOGNISED-SOURCE RESULT: one sentence.} These results
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
   belief), showing {RESULT}.
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

Design, hypotheses and analysis plan were pre-registered before data collection
(`PREREGISTRATION.md`, rev 3.1, commit `62535a8`). Deviations are listed in `DEVIATIONS.md`.

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

{FILL FROM models.yaml AND RUN LOGS}: GPT-OSS-120B, GPT-OSS-20B and Qwen3.8-27B via Groq;
Gemini 3.1 Flash-Lite and 3.5 Flash-Lite via Google AI Studio, each at full design (40 claims ×
6 conditions × 3 repetitions = 720 calls); Gemini 3.6 Flash as a spot check (10 claims × C0/C1 ×
3). Temperature 0.7; each model at its provider's lowest reasoning setting ({SETTINGS}). The
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
  certifies, judged by {JUDGE MODEL} on a stratified sample of {N} responses, with judge–human
  agreement on 30 hand-labelled items ({KAPPA}).

### 3.5 Analysis

Pairs are the unit of analysis. Six primary comparisons (C1 vs C0; C2 vs C3; C4 vs C1 and C3;
discrimination across conditions; scope accuracy across C1–C4; interpreter vs none) with Holm
correction. Inflation tests exclude pairs at ceiling in C0; the full sample is reported
alongside. Claim type enters as a factor throughout.

---

## 4. Results — written during the sprint

Fill every slot from `data/results_summary.md`. Report what the data shows, including nulls.

**4.1 Baseline.** C0 acceptance: real-obscure true {X}, false {X}; invented true {X}, false {X}.
{One sentence on whether invented claims were rejected at baseline.}

**4.2 Credence inflation (H1).** Figure 1: acceptance by condition, split by claim type and truth.
C1 vs C0 on false claims: {Δ, CI, p_holm}.

**4.3 Signal over semantics (H2).** C2 vs C3: {Δ, CI, p_holm}. C4 vs C1: {Δ, CI, p_holm}.
{One sentence: did models distinguish what the credentials certified?}

**4.4 Inflation without discrimination (H2b).** Figure 2: discrimination index by condition.
{Did the index stay flat across C0–C4 and rise at C5?}

**4.5 Justifications (H3).** Scope accuracy by condition {table}. Credential-citation rate
{table}. Example justifications: one correct, one misattributing a gathered assertion to the
signer (quote the model output verbatim, briefly).

**4.6 Unrecognised sources (H5).** C1 vs C0 on invented items: {Δ}. {Did a credential rescue
claims from organisations the model did not recognise?}

**4.7 Countermeasure (H4).** Interpreter vs none on C1/C2: {Δ, CI, p_holm}.

**4.8 Models.** Per-model table. 120B vs 20B. 3.1 vs 3.5 Flash-Lite. Spot check.

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

## Appendix A. Limitations and Dual-Use / Ethical Considerations (pre-sprint draft; required)

**What this study establishes.** Within single-turn evaluations of {N} open-weight and small
proprietary models, how acceptance and confidence in a fixed claim change when a credential is
attached, and whether models distinguish credentials that license different inferences.

**What it does not establish.**
- Behaviour of frontier models, which were tested only as a spot check or not at all.
- Behaviour in agentic loops, where a model retrieves, compares and cross-checks sources.
- Behaviour on cryptographically signed assets: credentials were presented as crJSON-style
  views, a derived format not intended as input and not independently verifiable.
- Effects of credential position, wording or format, which were held constant.
- Invented organisations are detectable by non-recognition (§3.1); the invented half therefore
  measures how credentials interact with unknown sources, not uncheckable facts.
- Scope accuracy relies on an LLM judge, validated against 30 human labels, with no second
  independent judge.
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
