# tests/test_client.py
import math

from src.llm.client import _media_geometrica, _trova_span_valore, _logprob_per_campo, MockLLMClient


def test_media_geometrica_penalizza_il_debole():
    # p = 0.22, 0.92, 0.92  → logprob = -1.51, -0.083, -0.083
    lp = [math.log(0.22), math.log(0.92), math.log(0.92)]
    geo = _media_geometrica(lp)
    aritm = (0.22 + 0.92 + 0.92) / 3
    assert geo < aritm          # la geometrica pesa di più il token incerto
    assert 0.50 < geo < 0.60


def test_trova_span():
    raw = '{"piva": "00743110157", "totale": "1234,64"}'
    start, end = _trova_span_valore(raw, "piva")
    assert raw[start:end] == "00743110157"


def test_span_mapping_esclude_la_struttura():
    """Il test che conta: i token delle graffe non devono entrare nella media."""
    raw = '{"piva":"007"}'
    tokens = [
        {"token": '{"', "logprob": -0.01},   # struttura: p≈0.99
        {"token": "piva", "logprob": -0.01},  # struttura
        {"token": '":"', "logprob": -0.01},   # struttura
        {"token": "0", "logprob": math.log(0.5)},   # VALORE: incerto
        {"token": "0", "logprob": math.log(0.5)},   # VALORE: incerto
        {"token": "7", "logprob": math.log(0.5)},   # VALORE: incerto
        {"token": '"}', "logprob": -0.01},    # struttura
    ]
    lp = _logprob_per_campo(raw, tokens, ["piva"])
    # solo i 3 token del valore → 0.5, non annacquato dai 4 a 0.99
    assert abs(lp["piva"] - 0.5) < 0.01


def test_mock():
    m = MockLLMClient({"piva_fornitore": "00743110157"}, {"piva_fornitore": 0.97})
    valori, lp, raw = m.extract("qualsiasi", ["piva_fornitore"])
    assert valori["piva_fornitore"] == "00743110157"
    assert lp["piva_fornitore"] == 0.97