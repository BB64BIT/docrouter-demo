"""Documenti sintetici precaricati.

NESSUN dato reale, mai. La struttura viene dalla conoscenza di dominio
(tracciato FatturaPA), non da fatture ENI copiate. In sala: "sono tutti
sintetici, nessun documento aziendale è mai uscito dal perimetro".

Il caso OCR_SPORCO è il FALLIMENTO NOTO, mostrato di proposito.
"""

DOCUMENTI: dict[str, dict] = {
    "pulito": {
        "label": "Fattura standard",
        "desc": "PDF nativo, campi tutti presenti",
        "testo": """FATTURA n. 2026/0042 del 15/07/2026

Fornitore: Eni S.p.A.
Piazzale Enrico Mattei 1, 00144 Roma
P.IVA IT 00743110157

Imponibile:        1.012,00 EUR
IVA 22%:             222,64 EUR
Totale documento:  1.234,64 EUR""",
    },
    "ocr_sporco": {
        "label": "Scansione degradata",
        "desc": "OCR confonde O/0 e l/1 — il limite noto del sistema",
        "testo": """FATTURA n. 2O26/OO42 del l5/O7/2O26

Fornitore: Eni S.p.A.
P.IVA IT OO743IIO157

Imponibile:        1.O12,OO EUR
IVA 22%:             222,64 EUR
Totale documento:  1.234,64 EUR""",
    },
    "piva_assente": {
        "label": "P.IVA mancante",
        "desc": "Il campo non c'è: il modello se lo inventa?",
        "testo": """FATTURA n. 2026/0043 del 16/07/2026

Fornitore: Eni S.p.A.
Piazzale Enrico Mattei 1, 00144 Roma

Imponibile:        2.500,00 EUR
IVA 22%:             550,00 EUR
Totale documento:  3.050,00 EUR""",
    },
    "incoerente": {
        "label": "Totale incoerente",
        "desc": "Ogni campo è perfetto. I tre insieme non tornano",
        "testo": """FATTURA n. 2026/0044 del 16/07/2026

Fornitore: Eni S.p.A.
P.IVA IT 00743110157

Imponibile:        1.012,00 EUR
IVA 22%:             222,64 EUR
Totale documento:  1.500,00 EUR""",
    },
    "piva_errata": {
        "label": "P.IVA con check digit errato",
        "desc": "11 cifre, formato perfetto, ma non è una P.IVA valida",
        "testo": """FATTURA n. 2026/0045 del 16/07/2026

Fornitore: Acme Forniture S.r.l.
P.IVA IT 00743110158

Imponibile:          500,00 EUR
IVA 22%:             110,00 EUR
Totale documento:    610,00 EUR""",
    },
}