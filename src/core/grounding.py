# src/core/grounding.py
"""Verifica di ancoraggio: il valore estratto è davvero sul documento?

Difesa contro il fallimento 3 — il valore formalmente perfetto che il
modello si è inventato. Non chiede niente al modello: cerca nel testo.
"""

from rapidfuzz import fuzz

from src.core.schema import GroundingMode


def _normalizza(testo: str) -> str:
    """Riduce due stringhe alla stessa forma prima di confrontarle.

    Senza questo, "IT 00743110157" sul PDF e "00743110157" estratto
    risulterebbero diversi: falso allarme su un valore corretto.
    """
    t = testo.upper()
    for c in [" ", ".", ",", "-", "/", ":", "\n", "\t", "'", '"']:
        t = t.replace(c, "")
    return t


def verifica_grounding(
    value: str,
    testo: str,
    modo: GroundingMode,
) -> float | None:
    """Ritorna un punteggio 0-100, o None se il grounding non si applica.

    None NON significa "fallito". Significa "domanda sbagliata":
    un campo derivato non è sul documento per definizione.
    """

    # --- Caso derived: esci subito ---
    # Cercare "22" (aliquota) nel testo darebbe un match casuale
    # su qualsiasi numero che contiene 22. Peggio che inutile: fuorviante.
    if modo == "derived":
        return None

    # --- Guardie ---
    if not value or not value.strip():
        return 0.0
    if not testo or not testo.strip():
        return 0.0

    v = _normalizza(value)
    t = _normalizza(testo)

    if not v:  # il valore era solo punteggiatura
        return 0.0

    # --- verbatim: c'è o non c'è ---
    if modo == "verbatim":
        return 100.0 if v in t else 0.0

    # --- fuzzy: quanto ci somiglia ---
    if modo == "fuzzy":
        # partial_ratio cerca la MIGLIORE corrispondenza del valore corto
        # dentro il testo lungo. ratio() confronterebbe l'intera fattura
        # con "ENI SPA" e darebbe ~2: sbagliato strumento.
        return float(fuzz.partial_ratio(v, t))

    raise ValueError(f"modo di grounding sconosciuto: {modo}")