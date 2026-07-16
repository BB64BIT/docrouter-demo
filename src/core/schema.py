# src/core/schema.py
"""Regole di dominio: cosa contiene una fattura e come si verifica ogni campo.

Questa è CONOSCENZA, non dato. Non si deduce dal documento: la scrivi tu,
una volta, perché sai come è fatta una fattura. Il pipeline la legge.
"""

from typing import Callable, Literal

from pydantic import BaseModel, ConfigDict, Field

from src.core import validators

# Il Literal blinda i valori ammessi: scrivere "verbatimm" esplode
# alla creazione della spec, non in produzione davanti ai colleghi.
GroundingMode = Literal["verbatim", "fuzzy", "derived"]


class FieldSpec(BaseModel):
    """Come si estrae e si verifica UN campo. Vale per tutte le fatture."""

    # Le funzioni come valore di campo hanno bisogno di questo:
    # Pydantic di default non sa validare un Callable.
    model_config = ConfigDict(arbitrary_types_allowed=True)

    name: str                      # chiave tecnica, es. "piva_fornitore"
    label: str                     # come appare in dashboard
    grounding_mode: GroundingMode  # ← la risposta alla domanda 2

    # Il validator è OPZIONALE: "ragione_sociale" non ha una regola
    # sintattica. Non tutti i campi si possono validare, e va bene.
    validator: Callable[[str], tuple[bool, str | None]] | None = None

    # Soglia fuzzy: ge/le impediscono di scriverci 150 per sbaglio.
    fuzzy_threshold: float = Field(default=85.0, ge=0.0, le=100.0)

    required: bool = True


# --- La spec della fattura ---
# Ogni riga è una decisione che devi saper difendere in sala.
FATTURA_SPEC: list[FieldSpec] = [
    FieldSpec(
        name="numero_fattura",
        label="Numero fattura",
        grounding_mode="verbatim",  # stampato tale e quale
        validator=None,             # nessun formato standard: ogni fornitore fa il suo
    ),
    FieldSpec(
        name="data_fattura",
        label="Data fattura",
        grounding_mode="verbatim",
        validator=validators.valida_data,
    ),
    FieldSpec(
        name="piva_fornitore",
        label="P.IVA fornitore",
        grounding_mode="verbatim",  # una cifra diversa = altra azienda. Mai fuzzy.
        validator=validators.valida_piva,
    ),
    FieldSpec(
        name="ragione_sociale_fornitore",
        label="Ragione sociale",
        grounding_mode="fuzzy",     # "Eni S.p.A." vs "ENI SPA"
        validator=None,
        fuzzy_threshold=85.0,
    ),
    FieldSpec(
        name="imponibile",
        label="Imponibile",
        grounding_mode="verbatim",
        validator=validators.valida_importo,
    ),
    FieldSpec(
        name="iva",
        label="IVA",
        grounding_mode="verbatim",
        validator=validators.valida_importo,
    ),
    FieldSpec(
        name="totale",
        label="Totale documento",
        grounding_mode="verbatim",  # È STAMPATO. Il check aritmetico è in più, non al posto.
        validator=validators.valida_importo,
    ),
    FieldSpec(
        name="aliquota_iva",
        label="Aliquota IVA",
        grounding_mode="derived",   # dedotta da iva/imponibile: non è scritta
        validator=None,
        required=False,
    ),
]

# Indice per accesso rapido: SPEC_BY_NAME["piva_fornitore"] invece di
# ciclare la lista ogni volta.
SPEC_BY_NAME: dict[str, FieldSpec] = {s.name: s for s in FATTURA_SPEC}