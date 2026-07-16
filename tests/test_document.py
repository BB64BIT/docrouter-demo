# tests/test_document.py
from src.core.document import ExtractedDocument
from src.core.fields import ExtractedField


def _f(name, value, is_valid=True, grounding=100.0, mode="verbatim", err=None):
    return ExtractedField(
        name=name, value=value, mean_logprob=1.0,
        is_valid=is_valid, validation_error=err,
        grounding=grounding, grounding_mode=mode,
    )


def _doc(imp="1.012,00 EUR", iva="222,64 EUR", tot="1.234,64 EUR", extra=None):
    fields = [_f("imponibile", imp), _f("iva", iva), _f("totale", tot)]
    if extra:
        fields.extend(extra)
    return ExtractedDocument(doc_id="test", testo="...", fields=fields)


def test_coerente_passa():
    d = _doc()
    assert d.coerenza_aritmetica is True
    assert d.routing == "auto"


def test_incoerenza_manda_in_review():
    """I 3 campi sono impeccabili presi da soli. Insieme mentono."""
    d = _doc(tot="1.500,00 EUR")
    assert all(f.routing == "auto" for f in d.fields)  # nessuno sospetto
    assert d.coerenza_aritmetica is False
    assert d.routing == "review"                        # ma il doc li ferma
    assert "Incoerenza" in d.reason


def test_campo_scartato_ha_precedenza():
    piva = _f("piva_fornitore", "00743110158", is_valid=False, err="check digit errato")
    d = _doc(tot="1.500,00 EUR", extra=[piva])
    assert d.routing == "reject"           # non review
    assert "piva_fornitore" in d.campi_scartati


def test_tolleranza_un_centesimo():
    d = _doc(tot="1.234,65 EUR")
    assert d.coerenza_aritmetica is True


def test_non_verificabile():
    d = _doc(iva="")
    assert d.coerenza_aritmetica is None
    assert d.routing == "auto"


def test_logprob_alto_non_salva_nulla():
    """La prova: mean_logprob=1.0 su tutto, e il doc va comunque in review."""
    d = _doc(tot="9.999,99 EUR")
    assert all(f.mean_logprob == 1.0 for f in d.fields)
    assert d.routing == "review"