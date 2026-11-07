# Verification Theatre

A pre-registered study for the Apart Research **AI x Epistemics Research Sprint**
(13–15 November 2026), Track 2: Trust Infrastructure.

When a document carries a C2PA / Content Credentials provenance mark, do language models
respond to what the mark actually certifies, or merely to the fact that a mark is present?
The hypotheses, design, measures and analysis plan are in
[PREREGISTRATION.md](PREREGISTRATION.md).

## Status

**No experimental data has been collected.** No model in the study has been queried, and
data collection does not begin until 13 November 2026. The claim corpus is still being
built.

## Work that predates the sprint

The sprint starts on 13 November 2026. The following were created before it:

- **Commit `69f332f`** (8 November 2026): the pre-registration (revision 2), the build
  notes in `CLAUDE.md`, five draft corpus claims, and `corpus/screen_names.py`.
- **`corpus/screen_names.py`** (written 6 November 2026): screens invented names against
  the GeoNames gazetteer, rejecting any within edit distance 2 of a real place
  (pre-registration §3).

Every commit dated before 13 November 2026 is pre-sprint work; the git history records
which files each one touched.

## Repository

| Path | Contents |
|---|---|
| `PREREGISTRATION.md` | Hypotheses, conditions, measures, analysis plan |
| `CLAUDE.md` | Build instructions for the codebase |
| `corpus/claims.jsonl` | Claim corpus: true/false twin pairs, invented and real-obscure |
| `corpus/screen_names.py` | Near-collision screen for invented names |
