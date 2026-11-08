# Status

Last updated 8 Nov 2026, before any data. Sprint runs 13–15 Nov 2026; build freeze Wed 11 Nov.
No study model has been queried.

## Done

- **Pre-registration rev 3.1** committed and public (`62535a8`). Revision history in §12.
- **Corpus**: 40 claims in 20 true/false twin pairs, `corpus/claims.jsonl`.
  - 10 real-obscure pairs, each checked verbatim against a primary source
    (`source_url`, `source_quote`).
  - 10 invented pairs mirroring the real pairs cell by cell (domain × jurisdiction ×
    alteration kind). Truth for invented items is the fictional record in `source_quote`.
  - Each half: 5 number and 5 date alterations. Numbers move 5 up and 5 down overall.
    Mean claim length 168 (invented) vs 165 (real) characters.
- **Name screening**: every invented name is clean in both passes of
  `corpus/screen_names.py` (GeoNames, edit distance ≤ 2) and has no web hits.
- **Closed-book probes**, run on a Claude model outside the study:
  - `corpus/obscurity_probe.json`: real pairs at chance apart from the old real-02,
    which was reworked. Its re-probe scored 60, below the flag line.
  - `corpus/realness_probe.json`: invented and real claims separated 20/20 by whether
    the model recognises the organisation. This prompted rev 3.
- **README** marks pre-sprint work.

## Key decisions

- Twins differ in exactly one span; `alteration` makes this machine-checkable. The pair
  is the unit of analysis (§7).
- No named-party alterations. They were removed after the obscurity probe; §3 permits
  but does not require them.
- Claim type means recognised vs unrecognised organisation (rev 3). The real-obscure half
  is the primary test of H1–H3; the invented half tests H5.
- Inflation tests exclude only pairs at ceiling in C0 (rev 3).
- One invented signer, identical in every condition; C4 changes only trust-list status.
- Reasoning effort fixed per model and logged with every call.

## File map

| Path | Contents |
|---|---|
| `PREREGISTRATION.md` | Design, hypotheses, measures, analysis plan |
| `CLAUDE.md` | Build instructions |
| `README.md` | Overview; pre-sprint work |
| `STATUS.md` | This file |
| `corpus/claims.jsonl` | The 40 claims |
| `corpus/screen_names.py` | Invented-name screen (two GeoNames passes) |
| `corpus/obscurity_probe.json` | Forced-choice obscurity probe, plus the real-02 re-probe |
| `corpus/realness_probe.json` | Real-vs-fabricated probe of the 20 true claims |

## Next steps (all by Wed 11 Nov)

1. `corpus/conditions/`: templates C0–C5 and the signer.
2. `src/build_documents.py`: exact messages per (claim, condition, interpreter), with tests
   and rendered examples.
3. Prompt wording and its tests.
4. `src/runner.py`, `src/providers/`, `models.yaml`, `--dry-run`.
5. `src/grade.py`: deterministic metrics first, then the LLM judge.
6. `src/analyse.py`, written against synthetic data.
7. Pilot: 5 claims, all conditions, one Groq and one Gemini model, capped at ~30 calls
   and disclosed.
8. Freeze. Run from 13 Nov; start the Gemini arm on Friday right after the 13:30 IST
   quota reset.
