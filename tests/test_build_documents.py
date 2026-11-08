"""Invariants of src/build_documents.py, checked for every claim, condition and interpreter setting."""
import copy
import datetime as dt
import inspect
import json
import re

import pytest

from src import build_documents as B

CTX = B.load_context()
CLAIMS = B.load_claims()
BY_ID = {c["id"]: c for c in CLAIMS}
PAIRS = sorted({c["pair_id"] for c in CLAIMS})
RUN_DATE = dt.date(2026, 11, 13)
MARKED = ("C1", "C2", "C3", "C4", "C5")
RUNS = [(c, False) for c in B.CONDITIONS] + [(c, True) for c in MARKED]


def user(claim, cond, interp=False):
    return B.build_messages(CTX, claim, cond, interp, RUN_DATE)[1]["content"]


def document_block(text):
    return re.search(r"<document>\n(.*?)\n</document>", text, re.S).group(1)


def m0(manifest):
    return manifest["manifests"][0]


# ---- required invariants

@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: c["id"])
def test_body_identical_across_conditions(claim):
    bodies = {document_block(user(claim, c, i)) for c, i in RUNS}
    assert bodies == {claim["text"]}
    # the document opens every user message, in the same bytes
    prefix = f"Document:\n<document>\n{claim['text']}\n</document>\n\n"
    assert all(user(claim, c, i).startswith(prefix) for c, i in RUNS)


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: c["id"])
def test_c2_c3_differ_only_in_assertion_bucket(claim):
    c2, c3 = (B.render_manifest(CTX, claim, c) for c in ("C2", "C3"))
    moved = m0(c2)["claim.v2"]["gathered_assertions"]
    assert len(moved) == 1 and moved[0]["url"].endswith(".statement")
    expect = copy.deepcopy(c2)
    m0(expect)["claim.v2"]["gathered_assertions"] = []
    m0(expect)["claim.v2"]["created_assertions"].append(moved[0])
    assert expect == c3
    # and nothing else in the message differs
    j2, j3 = B.manifest_json(c2), B.manifest_json(c3)
    assert user(claim, "C2").replace(j2, "<M>") == user(claim, "C3").replace(j3, "<M>")


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda c: c["id"])
def test_c4_c1_differ_only_in_trust_status(claim):
    c1, c4 = (B.render_manifest(CTX, claim, c) for c in ("C1", "C4"))
    r1, r4 = m0(c1)["validationResults"], m0(c4)["validationResults"]
    trusted = [e for e in r1["success"] if e["code"] == "signingCredential.trusted"]
    untrusted = [e for e in r4["failure"] if e["code"] == "signingCredential.untrusted"]
    assert len(trusted) == 1 and len(untrusted) == 1
    assert not any(e["code"].startswith("signingCredential") for e in r4["success"])
    a, b = copy.deepcopy(c1), copy.deepcopy(c4)
    m0(a)["validationResults"]["success"].remove(trusted[0])
    m0(b)["validationResults"]["failure"].remove(untrusted[0])
    assert a == b
    assert m0(c1)["signature"] == m0(c4)["signature"]  # same signer, same certificate


@pytest.mark.parametrize("pair_id", PAIRS)
@pytest.mark.parametrize("cond,interp", RUNS)
def test_twins_differ_only_in_altered_span(pair_id, cond, interp):
    t, f = BY_ID[pair_id + "-t"], BY_ID[pair_id + "-f"]
    a = f["alteration"]
    assert t["text"].replace(a["from"], a["to"], 1) == f["text"]
    ut, uf = user(t, cond, interp), user(f, cond, interp)
    assert ut.replace(t["text"], "<CLAIM>") == uf.replace(f["text"], "<CLAIM>")
    sys_t, sys_f = (B.build_messages(CTX, c, cond, interp, RUN_DATE)[0] for c in (t, f))
    assert sys_t == sys_f


# ---- further invariants

def test_deterministic():
    for c in CLAIMS:
        for cond, interp in RUNS:
            assert (B.build_messages(CTX, c, cond, interp, RUN_DATE)
                    == B.build_messages(CTX, c, cond, interp, RUN_DATE))


def test_signer_identical_in_every_condition_and_claim():
    sigs, gens = set(), set()
    for c in CLAIMS:
        for cond in MARKED:
            m = m0(B.render_manifest(CTX, c, cond))
            sigs.add(json.dumps(m["signature"], sort_keys=True))
            gens.add(json.dumps(m["claim.v2"]["claim_generator_info"], sort_keys=True))
    assert len(sigs) == 1 and len(gens) == 1
    assert "Vellumworth Document Services Ltd" in next(iter(sigs))


def test_manifest_position_constant():
    for c in CLAIMS:
        for cond in MARKED:
            u = user(c, cond)
            doc_end = u.index("</document>") + len("</document>")
            assert u[doc_end:].startswith("\n\nThe retrieval tool reported the following Content Credentials")
            assert u.index("```json") < u.index("Based on the document")


def test_c0_has_no_manifest():
    for c in CLAIMS:
        u = user(c, "C0")
        assert "```json" not in u and "Content Credentials" not in u and "C2PA" not in u


def test_c5_binds_statement_to_source_quote():
    for c in CLAIMS:
        stmt = m0(B.render_manifest(CTX, c, "C5"))["assertions"]["com.vellumworth.statement"]
        assert stmt["schema:text"] == c["text"]
        assert stmt["schema:isBasedOn"] == {"@type": "schema:Quotation", "schema:text": c["source_quote"]}
        assert stmt == {**m0(B.render_manifest(CTX, c, "C3"))["assertions"]["com.vellumworth.statement"],
                        "schema:isBasedOn": stmt["schema:isBasedOn"]}


def test_interpreter_uses_only_the_manifest():
    assert list(inspect.signature(B.render_interpreter).parameters) == ["manifest"]
    for c in CLAIMS:
        for cond in MARKED:
            man = B.render_manifest(CTX, c, cond)
            text, blob = B.render_interpreter(man), B.manifest_json(man)
            for quoted in re.findall(r'"([^"]+)"', text):
                assert quoted in blob
            m = m0(man)
            for value in (m["signature"]["certificateInfo"]["subject"]["O"],
                          m["signature"]["certificateInfo"]["issuer"]["O"],
                          m["claim.v2"]["claim_generator_info"]["name"]):
                assert value in blob
            assert all(line.endswith(".") for line in text.splitlines())


def test_interpreter_scope_sentences():
    c = BY_ID["real-03-t"]
    it = {cond: B.render_interpreter(B.render_manifest(CTX, c, cond)) for cond in MARKED}
    assert "None of the signed assertions says whether" in it["C1"]
    assert "is a gathered assertion" in it["C2"] and "not attributed to the signer" in it["C2"]
    assert "is a created assertion" in it["C3"] and "is asserting it" in it["C3"]
    assert "not on any of the validator's trust lists" in it["C4"]
    assert "on the validator's trust list" in it["C1"] and "not on any" not in it["C1"]
    assert c["source_quote"] in it["C5"]


def test_no_ids_or_truth_labels_leak():
    for c in CLAIMS:
        for cond, interp in RUNS:
            msgs = B.build_messages(CTX, c, cond, interp, RUN_DATE)
            blob = json.dumps(msgs, ensure_ascii=False)
            assert not re.search(r"\b(inv|real)-\d\d", blob)
            assert "truth_value" not in blob and "pair_id" not in blob
            if c["source_url"]:
                assert c["source_url"] not in blob


def test_interpreter_rejected_for_c0():
    with pytest.raises(ValueError):
        B.build_messages(CTX, CLAIMS[0], "C0", True, RUN_DATE)
