# tests/test_fields.py
from src.core.fields import ExtractedField


def _campo(**kw):
    base = dict(
        name="piva_fornitore",
        value="00743110157",
        mean_logprob=0.99,
        is_valid=True,
        grounding=100.0,
        grounding_mode="verbatim",
    )
    return ExtractedField(**{**base, **kw})


def test_campo_perfetto():
    c = _campo()
    assert c.confidence == 0.99
    assert c.routing == "auto"


def test_gate_validazione_annulla_logprob_alto():
    """IL TEST CHIAVE: modello sicurissimo, valore invalido → 0, non media."""
    c = _campo(is_valid=False, validation_error="check digit errato", mean_logprob=0.99)
    assert c.confidence == 0.0       # non 0.66
    assert c.routing == "reject"
    assert "check digit" in c.reason


def test_gate_grounding_becca_allucinazione():
    """Valore formalmente valido, modello sicuro, ma non è sul documento."""
    c = _campo(value="12345678903", is_valid=True, mean_logprob=0.99, grounding=0.0)
    assert c.confidence == 0.0
    assert c.routing == "reject"
    assert "allucinazione" in c.reason


def test_modello_incerto_va_in_review():
    c = _campo(mean_logprob=0.75)
    assert c.routing == "review"
    assert "Verifica umana" in c.reason


def test_derived_non_blocca():
    """grounding=None non è un fallimento: è fuori scope."""
    c = _campo(name="aliquota_iva", value="22", grounding=None, grounding_mode="derived")
    assert c.is_grounded is True
    assert c.confidence == 0.99
    assert c.routing == "auto"


def test_fuzzy_sopra_soglia():
    c = _campo(name="ragione_sociale_fornitore", value="ENI SPA",
               grounding=87.0, grounding_mode="fuzzy")
    assert c.routing == "auto"


def test_fuzzy_sotto_soglia():
    c = _campo(name="ragione_sociale_fornitore", value="ACME",
               grounding=40.0, grounding_mode="fuzzy")
    assert c.confidence == 0.0
    assert "Somiglianza insufficiente" in c.reason