# src/core/document.py
"""Il documento: i campi insieme, e i controlli che li attraversano.

Perché esiste questo livello: la coerenza aritmetica (imponibile + iva
== totale) ha bisogno di TRE campi contemporaneamente. Nessun
ExtractedField può farla — conosce solo sé stesso.
"""

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, computed_field

from src.core.fields import ExtractedField
from src.core.validators import parse_importo

DocRouting = Literal["auto", "review", "reject"]

# Tolleranza sull'arrotondamento: 1 centesimo.
TOLLERANZA = Decimal("0.01")


class ExtractedDocument(BaseModel):
    doc_id: str
    testo: str
    fields: list[ExtractedField]

    @computed_field
    @property
    def by_name(self) -> dict[str, str]:
        """Mappa campo → valore, per accesso rapido."""
        return {f.name: f.value for f in self.fields}

    @computed_field
    @property
    def coerenza_aritmetica(self) -> bool | None:
        """imponibile + iva == totale?

        None = non verificabile (campi mancanti o non parsabili).
        Come per il grounding: None NON è un fallimento, è "domanda
        non applicabile".
        """
        v = self.by_name
        imp = parse_importo(v.get("imponibile", ""))
        iva = parse_importo(v.get("iva", ""))
        tot = parse_importo(v.get("totale", ""))

        if imp is None or iva is None or tot is None:
            return None

        return abs((imp + iva) - tot) <= TOLLERANZA

    @computed_field
    @property
    def campi_scartati(self) -> list[str]:
        return [f.name for f in self.fields if f.routing == "reject"]

    @computed_field
    @property
    def routing(self) -> DocRouting:
        """Il documento sovrascrive i campi.

        Ordine: un campo rotto è peggio di un'incoerenza. Se la P.IVA
        è inventata, l'aritmetica non conta più.
        """
        if self.campi_scartati:
            return "reject"

        # L'aritmetica non torna: i tre campi sono ognuno impeccabile
        # (validi, ancorati, logprob 1.0) ma insieme mentono.
        # Non sappiamo QUALE: serve un umano.
        if self.coerenza_aritmetica is False:
            return "review"

        return "auto"

    @computed_field
    @property
    def reason(self) -> str:
        if self.campi_scartati:
            return f"Campi non validati: {', '.join(self.campi_scartati)}"

        if self.coerenza_aritmetica is False:
            v = self.by_name
            return (
                f"Incoerenza aritmetica: {v.get('imponibile')} + {v.get('iva')} "
                f"≠ {v.get('totale')}. Impossibile stabilire quale campo sia "
                f"errato: revisione manuale."
            )

        if self.coerenza_aritmetica is None:
            return "Estratto. Coerenza aritmetica non verificabile (campi mancanti)"

        return "Tutti i campi validati e coerenti"
    
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