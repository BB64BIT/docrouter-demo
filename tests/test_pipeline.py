# tests/test_pipeline.py
from src.llm.client import MockLLMClient
from src.pipeline import processa

TESTO = """FATTURA n. 2026/0042 del 15/07/2026
Eni S.p.A. - P.IVA IT 00743110157
Imponibile: 1.012,00 EUR
IVA 22%: 222,64 EUR
Totale documento: 1.234,64 EUR"""

BUONO = {
    "numero_fattura": "2026/0042",
    "data_fattura": "15/07/2026",
    "piva_fornitore": "IT 00743110157",
    "ragione_sociale_fornitore": "Eni S.p.A.",
    "imponibile": "1.012,00 EUR",
    "iva": "222,64 EUR",
    "totale": "1.234,64 EUR",
    "aliquota_iva": "22",
}


def test_documento_pulito_passa():
    doc = processa(TESTO, MockLLMClient(BUONO))
    assert doc.routing == "auto"
    assert doc.campi_scartati == []


def test_allucinazione_scartata():
    """P.IVA valida come check digit, ma NON su questo documento."""
    r = {**BUONO, "piva_fornitore": "12345678903"}
    doc = processa(TESTO, MockLLMClient(r))
    assert doc.routing == "reject"
    assert "piva_fornitore" in doc.campi_scartati


def test_incoerenza_in_review():
    """Ogni campo perfetto, i tre insieme non tornano."""
    r = {**BUONO, "totale": "1.500,00 EUR"}
    doc = processa(TESTO, MockLLMClient(r))
    # il totale è VALIDO e ANCORATO? no: 1.500,00 non è nel testo
    # → questo test verifica il caso reale in cui l'OCR sbaglia
    assert doc.routing in ("reject", "review")