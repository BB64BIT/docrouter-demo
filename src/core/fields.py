# src/core/fields.py
"""Un campo estratto + le prove che lo sostengono.

Architettura della confidence:
  - is_valid (C)   → GATE: fallisce → confidence 0, fine
  - is_grounded    → GATE: fallisce → confidence 0, fine
  - mean_logprob (B) → il numero graduale, valutato SOLO dopo i gate

Nessuna media pesata: un valore invalido non è "mediamente buono".
"""

from typing import Literal

from pydantic import BaseModel, Field, computed_field

from src.core.schema import GroundingMode

RoutingDecision = Literal["auto", "review", "reject"]

class ExtractedField(BaseModel):
    """Un campo, il suo valore, e tutte le prove raccolte su di esso."""

    name: str
    value: str

    # --- B: logprobs. Media delle probabilità dei token del campo. ---
    mean_logprob: float = Field(ge=0.0, le=1.0)

    # --- C: validazione sintattica ---
    is_valid: bool
    validation_error: str | None = None

    # --- Grounding: None = non applicabile (campo derived) ---
    grounding: float | None = Field(default=None, ge=0.0, le=100.0)
    grounding_mode: GroundingMode
    fuzzy_threshold: float = Field(default=85.0, ge=0.0, le=100.0)

    @computed_field
    @property
    def is_grounded(self) -> bool:
        """Il gate del grounding: punteggio → sì/no.

        La soglia sta QUI, non in grounding.py: lì si misura, qui si giudica.
        Così il punteggio grezzo resta visibile in dashboard.
        """
        # None = campo derived = la domanda non si applica.
        # NON bloccare: non è un fallimento, è fuori scope.
        if self.grounding is None:
            return True

        # verbatim: o c'è o non c'è. Nessuna tolleranza.
        if self.grounding_mode == "verbatim":
            return self.grounding >= 100.0

        # fuzzy: soglia dichiarata nella FieldSpec
        return self.grounding >= self.fuzzy_threshold

    @computed_field
    @property
    def confidence(self) -> float:
        """Solo i gate. B è stato scartato: satura a 1.0 anche su spazzatura.

        Misurato: OCR degradato ("OO743IIO157") → mean_logprob 1.0000
        a temperatura 0 e 0.7. Il modello copia, non genera: non ha
        incertezza da riportare.
        """
        if not self.is_valid:
            return 0.0
        if not self.is_grounded:
            return 0.0

        # L'unica gradazione reale rimasta: il punteggio fuzzy.
        if self.grounding_mode == "fuzzy" and self.grounding is not None:
            return self.grounding / 100.0

        return 1.0

    @computed_field
    @property
    def routing(self) -> RoutingDecision:
        """A livello campo il verdetto è binario. Il 'review' lo decide
        il documento, che vede i campi insieme."""
        if not self.is_valid or not self.is_grounded:
            return "reject"
        return "auto"
    
    
    @computed_field
    @property
    def reason(self) -> str:
        """Il PERCHÉ, in italiano, per la dashboard."""
        if not self.is_valid:
            return f"Validazione fallita: {self.validation_error}"

        if not self.is_grounded:
            if self.grounding_mode == "verbatim":
                return "Valore non presente nel documento (possibile allucinazione)"
            return (
                f"Somiglianza insufficiente: {self.grounding:.0f} "
                f"< soglia {self.fuzzy_threshold:.0f}"
            )

        if self.grounding_mode == "fuzzy":
            return f"Verificato. Somiglianza {self.grounding:.0f}/100"
        return "Verificato: valido e presente nel documento"