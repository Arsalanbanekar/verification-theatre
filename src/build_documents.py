"""Turn (claim, condition, interpreter on/off) into the exact chat messages sent to a model.

Everything except load_context(), load_claims() and the CLI is pure: the same inputs always
give byte-identical output, with no network access and no file writes.

Invariants (enforced in tests/test_build_documents.py):
- the document body is byte-identical across conditions;
- C2 and C3 differ only in which assertion list references the statement;
- C4 differs from C1 only in trust-list status;
- twins differ only in the altered span;
- the manifest block sits in the same position, right after the document, in C1-C5.

CLI:  python src/build_documents.py --examples corpus/rendered_examples
"""
from __future__ import annotations

import argparse
import base64
import copy
import datetime as dt
import hashlib
import json
import re
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path

try:
    from . import prompt_text as P
except ImportError:  # run as a script
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import prompt_text as P

REPO = Path(__file__).resolve().parents[1]
CONDITIONS = ("C0", "C1", "C2", "C3", "C4", "C5")
_PLACEHOLDER = re.compile(r"\{\{([^{}]+)\}\}")
_UUID_NS = uuid.UUID("6f1d2c3b-8a4e-5b7c-9d0e-1f2a3b4c5d6e")


@dataclass(frozen=True)
class Context:
    templates: dict  # condition -> template dict as loaded (metadata keys included)
    signer: dict     # placeholder -> value (keys starting "_" are notes)


def load_context(root: Path = REPO) -> Context:
    cdir = Path(root) / "corpus" / "conditions"
    templates = {c: json.loads((cdir / f"{c}.json").read_text(encoding="utf-8")) for c in CONDITIONS}
    signer = json.loads((cdir / "signer.json").read_text(encoding="utf-8"))
    return Context(templates=templates, signer=signer)


def load_claims(root: Path = REPO) -> list[dict]:
    with open(Path(root) / "corpus" / "claims.jsonl", encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


# ---------------------------------------------------------------- manifest rendering

def _hash(pair_id: str, key: str) -> str:
    digest = hashlib.sha256(f"{pair_id}|{key}".encode("utf-8")).digest()
    return "b64'" + base64.b64encode(digest).decode("ascii")


def _uuid(pair_id: str, kind: str) -> str:
    return str(uuid.uuid5(_UUID_NS, f"{kind}/{pair_id}"))


def _values(ctx: Context, claim: dict) -> dict:
    v = {k: val for k, val in ctx.signer.items() if not k.startswith("_")}
    pid = claim["pair_id"]
    v.update(MANIFEST_URN="urn:c2pa:" + _uuid(pid, "manifest"),
             INSTANCE_ID="xmp:iid:" + _uuid(pid, "instance"),
             STATEMENT=claim["text"],
             SOURCE_QUOTE=claim["source_quote"])
    return v


def _fill(obj, values: dict, pair_id: str):
    if isinstance(obj, dict):
        return {_fill(k, values, pair_id): _fill(val, values, pair_id) for k, val in obj.items()}
    if isinstance(obj, list):
        return [_fill(x, values, pair_id) for x in obj]
    if isinstance(obj, str):
        def sub(m):
            key = m.group(1)
            if key.startswith("HASH:"):
                return _hash(pair_id, key[5:])
            return values[key]  # KeyError on an unknown placeholder is deliberate
        return _PLACEHOLDER.sub(sub, obj)
    return obj


def render_manifest(ctx: Context, claim: dict, condition: str) -> dict | None:
    """The crJSON view for this claim and condition, or None for C0."""
    template = ctx.templates[condition]["manifest"]
    if template is None:
        return None
    return _fill(copy.deepcopy(template), _values(ctx, claim), claim["pair_id"])


def manifest_json(manifest: dict) -> str:
    return json.dumps(manifest, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- interpreter

def _date_words(iso: str) -> str:
    d = dt.datetime.fromisoformat(iso.replace("Z", "+00:00")).date()
    return f"{d.day} {d:%B %Y}"


def render_interpreter(manifest: dict) -> str:
    """Plain-language scope summary, one sentence per fact, built only from manifest fields.

    Facts: who signed; what the credentials record (how the file was made); integrity; trusted
    vs merely valid; for each statement assertion, created (attributed) vs gathered (not
    attributed); for a bound source, its excerpt. Nothing outside the manifest is used.
    """
    m = manifest["manifests"][0]
    cert = m["signature"]["certificateInfo"]
    signer, issuer = cert["subject"]["O"], cert["issuer"]["O"]
    gen = m["claim.v2"]["claim_generator_info"]
    created = next(a for a in m["assertions"]["c2pa.actions.v2"]["actions"] if a["action"] == "c2pa.created")
    ok = {e["code"] for e in m["validationResults"]["success"]}
    bad = {e["code"] for e in m["validationResults"]["failure"]}

    lines = [
        f"These credentials were signed by {signer}, using a certificate issued by {issuer}.",
        f"They record that the document was created with {gen['name']} {gen['version']} on {_date_words(created['when'])}.",
    ]
    if "assertion.dataHash.match" in ok:
        lines.append("The validator found that the document has not been changed since it was signed.")
    if "claimSignature.validated" in ok:
        if "signingCredential.trusted" in ok:
            lines.append("The signature is valid and the signing certificate is on the validator's trust list.")
        elif "signingCredential.untrusted" in bad:
            lines.append("The signature is valid, but the signing certificate is not on any of the validator's trust lists.")

    created_urls = {r["url"] for r in m["claim.v2"]["created_assertions"]}
    gathered_urls = {r["url"] for r in m["claim.v2"]["gathered_assertions"]}
    statements = [(label, a) for label, a in m["assertions"].items()
                  if isinstance(a, dict) and a.get("@type") == "schema:Claim"]
    if not statements:
        lines.append("None of the signed assertions says whether anything in the document is accurate.")
    for label, a in statements:
        url = f"self#jumbf=c2pa.assertions/{label}"
        text = a["schema:text"]
        if url in created_urls:
            lines.append(f'The statement "{text}" is a created assertion, so it is attributed to the signer: {signer} is asserting it.')
        elif url in gathered_urls:
            lines.append(f'The statement "{text}" is a gathered assertion: it was collected by the signer\'s software and is not attributed to the signer.')
        source = a.get("schema:isBasedOn")
        if isinstance(source, dict) and source.get("@type") == "schema:Quotation":
            lines.append(f'The credentials link that statement to this quoted source record: "{source["schema:text"]}".')
    return "\n".join(lines)


# ---------------------------------------------------------------- messages

def document_body(claim: dict) -> str:
    """The document the model sees: identical in every condition."""
    return claim["text"]


def format_run_date(run_date: dt.date) -> str:
    return f"{run_date.day} {run_date:%B %Y}"


def build_messages(ctx: Context, claim: dict, condition: str, interpreter: bool,
                   run_date: dt.date) -> list[dict]:
    """The exact chat messages for one call."""
    if condition not in CONDITIONS:
        raise ValueError(f"unknown condition {condition!r}")
    manifest = render_manifest(ctx, claim, condition)
    if interpreter and manifest is None:
        raise ValueError("the interpreter needs a manifest; C0 has none")

    parts = [f"{P.DOCUMENT_INTRO}\n<document>\n{document_body(claim)}\n</document>"]
    if manifest is not None:
        parts.append(f"{P.MANIFEST_INTRO}\n```json\n{manifest_json(manifest)}\n```")
    if interpreter:
        parts.append(f"{P.INTERPRETER_INTRO}\n{render_interpreter(manifest)}")
    parts.append(f"{P.QUESTION}\n\nStatement: {claim['text']}")
    parts.append(P.OUTPUT_INSTRUCTIONS)

    return [
        {"role": "system", "content": P.SYSTEM.format(run_date=format_run_date(run_date))},
        {"role": "user", "content": "\n\n".join(parts)},
    ]


def prompt_hash(messages: list[dict]) -> str:
    blob = json.dumps(messages, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------- CLI: rendered examples

EXAMPLE_CLAIMS = ("inv-03-t", "real-03-t")
EXAMPLE_RUN_DATE = dt.date(2026, 11, 13)


def write_examples(out_dir: Path, root: Path = REPO) -> list[Path]:
    ctx, claims = load_context(root), {c["id"]: c for c in load_claims(root)}
    out_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for cid in EXAMPLE_CLAIMS:
        runs = [(c, False) for c in CONDITIONS] + [("C1", True), ("C2", True)]
        for cond, interp in runs:
            msgs = build_messages(ctx, claims[cid], cond, interp, EXAMPLE_RUN_DATE)
            name = f"{cid}__{cond}{'__interpreter' if interp else ''}.txt"
            body = f"[system]\n{msgs[0]['content']}\n\n[user]\n{msgs[1]['content']}\n"
            path = out_dir / name
            path.write_text(body, encoding="utf-8", newline="\n")
            written.append(path)
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--examples", type=Path, help="write the rendered examples to this directory")
    a = ap.parse_args(argv)
    if a.examples:
        for p in write_examples(a.examples):
            print(p)


if __name__ == "__main__":
    main()
