# Condition templates

One file per condition. Each holds metadata (`_condition`, `_mark`, `_licenses`, `_notes`,
stripped before rendering) and a `manifest`: a crJSON-style view with `{{PLACEHOLDERS}}`.
`_notes` lists every simplification against the spec.

`src/build_documents.py` fills the placeholders:

- signer fields from `signer.json`, identical in every condition and every claim;
- `MANIFEST_URN`, `INSTANCE_ID` and `HASH:*` from the pair id, so twins and conditions
  share them (they are not computed over the content);
- `STATEMENT`: the claim sentence; `SOURCE_QUOTE`: the claim's `source_quote` (C5 only).

| File | Mark | Differs from |
|---|---|---|
| `C0.json` | none | — |
| `C1.json` | trusted signer; creation info and `c2pa.actions.v2` (plus the mandatory hard binding) | — |
| `C2.json` | statement assertion referenced from `gathered_assertions` | C1 + that assertion |
| `C3.json` | the same statement referenced from `created_assertions` | C2: bucket only |
| `C4.json` | `signingCredential.trusted` (success) → `signingCredential.untrusted` (failure) | C1: trust status only |
| `C5.json` | statement bound to a verbatim excerpt of its source record (`schema:isBasedOn`) | C3 + the excerpt |

The manifest block follows the document in every condition C1–C5, so mark position is
constant. The differences in the table are enforced by `tests/test_build_documents.py`.

Sources: [C2PA 2.4](https://spec.c2pa.org/specifications/specifications/2.4/specs/C2PA_Specification.html),
[crJSON 2.4](https://spec.c2pa.org/specifications/specifications/2.4/crJSON/crjson-format.html).
