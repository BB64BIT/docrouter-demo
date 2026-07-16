# tests/test_grounding.py
from src.core.grounding import verifica_grounding

TESTO = """
FATTURA n. 2026/0042 del 15/07/2026
Eni S.p.A. - P.IVA IT 00743110157
Imponibile: 1.012,00 EUR
IVA 22%: 222,64 EUR
Totale documento: 1.234,64 EUR
"""


def test_verbatim_trovato():
    assert verifica_grounding("00743110157", TESTO, "verbatim") == 100.0

def test_verbatim_con_rumore_normalizzato():
    # Sul documento c'è "IT 00743110157": la normalizzazione li allinea
    assert verifica_grounding("IT 00743110157", TESTO, "verbatim") == 100.0

def test_verbatim_allucinato():
    # P.IVA formalmente valida (check digit ok) ma NON su questo documento.
    # È il fallimento 3: C dice ok, B dice ok, solo il grounding lo becca.
    assert verifica_grounding("12345678903", TESTO, "verbatim") == 0.0

def test_fuzzy_ragione_sociale():
    score = verifica_grounding("ENI SPA", TESTO, "fuzzy")
    assert score >= 85.0

def test_fuzzy_azienda_sbagliata():
    score = verifica_grounding("ACME CORPORATION", TESTO, "fuzzy")
    assert score < 85.0

def test_derived_ritorna_none():
    # "22" non si cerca nel testo: la domanda non ha senso
    assert verifica_grounding("22", TESTO, "derived") is None

def test_valore_vuoto():
    assert verifica_grounding("", TESTO, "verbatim") == 0.0