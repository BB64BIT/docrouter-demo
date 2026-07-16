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