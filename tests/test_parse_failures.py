"""parse_failures.py: failure types, where failures fall, and whether they concentrate in a condition."""
import pandas as pd
import pytest

from src import parse_failures as PF

LOOP = '{"accept": "true", "confidence": 100, "justification": "x", "categories' + "_or_points" * 20


@pytest.mark.parametrize("text,kind", [
    ('{"accept": "true", "confidence": 95, "justification": "Signed.", "document_source_sign"}',
     "wrong key instead of reasons"),
    ('{"accept": "true", "confidence": 100, "justification": "The signature is trusted.", " Vac',
     "wrong key instead of reasons"),
    ('{"accept": "uncertain", "confidence": 15, "justification": "Cannot say.",', "reasons missing"),
    ('{"accept": "uncertain", "confidence": 15, "justification": "Cannot say."}', "reasons missing"),
    ('{"accept": "true", "confidence": 95, "justification": "x", "reasons": ["document_signiture"]}',
     "invalid reason code"),
    ('{"accept": "true", "confidence": 95, "justification": "x", "reasons": ["cited_e Dining', "invalid reason code"),
    ('{" activists', "derailed at the start"),
    ("{accept=true confidence=[Red", "derailed at the start"),
    ("not json", "derailed at the start"),
    (LOOP, "repetition loop"),
    ('{"accept": "uncertain", "confidence": 85, "justification": "The authority cannot be verified. Therefore',
     "cut off inside the justification"),
    ('{"accept": "true", "confidence": 90, "justification": "x", "reasons": ["prior_knowledge"]}', "other"),
])
def test_classify(text, kind):
    assert PF.classify(text) == kind
    assert PF.TYPES[kind] in ("wrong field name", "repetition loop", "truncation", "other")


def frame(rates: dict, n=100, model="m"):
    """rates: arm -> failure rate; n cells per arm, failures first."""
    rows = []
    for a, r in rates.items():
        k = round(r * n)
        rows += [{"model": model, "arm": a, "condition": a.split("+")[0], "interpreter": a.endswith("+I"),
                  "claim_id": f"c{i % 10}", "failed": i < k, "text": ""} for i in range(n)]
    return pd.DataFrame(rows)


def test_a_concentrated_condition_is_flagged():
    rates = {a: 0.05 for a in PF.ARMS} | {"C4": 0.30}
    c = PF.concentration(frame(rates), "m")
    assert c["over_double"] == ["C4"] and c["max_arm"] == "C4" and c["p"] < 0.001 and c["dof"] == 7
    assert "C4 exceeded twice the model's rate" in PF.concentration_text(c)
    t = PF.by_arm(frame(rates))
    assert list(t["arm"]) == list(PF.ARMS) and t.set_index("arm").loc["C4", "failed"] == 30


def test_even_failures_are_not_flagged_and_the_interpreter_is_compared():
    rates = {a: 0.10 for a in PF.ARMS}
    c = PF.concentration(frame(rates), "m")
    assert c["over_double"] == [] and c["p"] > 0.5 and c["interp_rate"] == c["no_interp_rate"] == 0.10
    text = PF.concentration_text(c)
    assert "no condition exceeded twice" in text and "do not differ reliably" in text


def test_a_model_without_failures():
    c = PF.concentration(frame({a: 0.0 for a in PF.ARMS[:6]}), "m")
    assert PF.concentration_text(c) == "m: no parse failures in 600 cells."
