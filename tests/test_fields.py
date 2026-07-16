from src.core.fields import ExtractedField


def _campo(**kw):
    base = dict(
        name="piva_fornitore",
        value="00743110157",
        mean_logprob=1.0,      # sempre ~1.0: il modello copia, non genera
        is_valid=True,
        grounding=100.0,
        grounding_mode="verbatim",
    )
    return ExtractedField(**{**base, **kw})


def test_campo_perfetto():
    c = _campo()
    assert c.confidence == 1.0
    assert c.routing == "auto"


def test_gate_validazione_annulla_logprob_alto():
    """Modello sicurissimo, valore invalido → 0. Nessuna media, nessuna pietà."""
    c = _campo(is_valid=False, validation_error="check digit errato")
    assert c.confidence == 0.0
    assert c.routing == "reject"
    assert "check digit" in c.reason


def test_gate_grounding_becca_allucinazione():
    c = _campo(value="12345678903", grounding=0.0)
    assert c.confidence == 0.0
    assert c.routing == "reject"
    assert "allucinazione" in c.reason


def test_logprob_non_influenza_piu_nulla():
    """LA PROVA CHE B È FUORI: logprob 0.10 vs 1.0, stesso esito.

    Misurato sul pod: OCR degradato 'OO743IIO157' → mean_logprob 1.0000
    a temperatura 0 E 0.7. Il modello copia dal contesto: non ha
    incertezza da riportare. B non discrimina, quindi non decide.
    """
    basso = _campo(mean_logprob=0.10)
    alto = _campo(mean_logprob=1.00)
    assert basso.confidence == alto.confidence == 1.0
    assert basso.routing == alto.routing == "auto"


def test_derived_non_blocca():
    """grounding=None non è un fallimento: è 'domanda non applicabile'."""
    c = _campo(name="aliquota_iva", value="22", grounding=None, grounding_mode="derived")
    assert c.is_grounded is True
    assert c.confidence == 1.0
    assert c.routing == "auto"


def test_fuzzy_e_lunica_gradazione_rimasta():
    """Con B fuori, il punteggio fuzzy è l'unico numero non binario."""
    c = _campo(name="ragione_sociale_fornitore", value="ENI SPA",
               grounding=87.0, grounding_mode="fuzzy")
    assert c.confidence == 0.87        # non 1.0: il fuzzy gradua
    assert c.routing == "auto"


def test_fuzzy_sotto_soglia():
    c = _campo(name="ragione_sociale_fornitore", value="ACME",
               grounding=40.0, grounding_mode="fuzzy")
    assert c.confidence == 0.0
    assert c.routing == "reject"
    assert "Somiglianza insufficiente" in c.reason