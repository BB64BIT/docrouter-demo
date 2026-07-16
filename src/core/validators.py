# src/core/validators.py
"""Validazione sintattica dei campi estratti (la "C" del confidence gating).

Nessuna di queste funzioni conosce l'LLM. Ricevono testo grezzo e dicono
se quel testo è un valore valido. Deterministiche, testabili, spiegabili.
"""

from datetime import datetime
from decimal import Decimal, InvalidOperation

FORMATI_DATA = ["%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d.%m.%Y"]


def valida_piva(value: str) -> tuple[bool, str | None]:
    """Verifica una Partita IVA italiana: 11 cifre + check digit."""

    # --- 1. GUARDIA: input assente ---
    # `not value` è True per None e per "". Li copre entrambi in un colpo.
    if not value or not value.strip():
        return False, "campo vuoto"

    # --- 2. NORMALIZZAZIONE ---
    # Il modello estrae quello che vede: "IT 00743110157", "it-00743110157"...
    # Vanno tutte ricondotte alla stessa forma prima di giudicare.
    pulito = value.strip().upper()

    # I replace si concatenano: ognuno lavora sul risultato del precedente.
    for carattere in [" ", ".", "-", "/"]:
        pulito = pulito.replace(carattere, "")

    # removeprefix (Python 3.9+) toglie "IT" SOLO se sta all'inizio.
    # Più sicuro di replace("IT", ""), che lo toglierebbe ovunque.
    pulito = pulito.removeprefix("IT")

    # --- 3. GUARDIE DI FORMA (separate: ogni errore ha il suo messaggio) ---
    if len(pulito) != 11:
        return False, f"lunghezza errata: {len(pulito)} cifre invece di 11 ('{value}')"

    if not pulito.isdigit():
        return False, f"contiene caratteri non numerici: '{value}'"

    # --- 4. IL CALCOLO VERO: check digit (variante Luhn) ---
    somma = 0

    # enumerate() restituisce coppie (indice, carattere).
    # [:10] = le prime 10 cifre; l'11ª è il check digit, non entra nella somma.
    for indice, carattere in enumerate(pulito[:10]):
        cifra = int(carattere)

        if indice % 2 == 0:
            # Indice pari (0,2,4...) = posizione DISPARI (1ª,3ª,5ª). Somma diretta.
            somma += cifra
        else:
            # Indice dispari = posizione PARI. Raddoppia; se supera 9, sottrai 9.
            doppio = cifra * 2
            somma += doppio - 9 if doppio > 9 else doppio

    # Il check digit è quanto manca al multiplo di 10 successivo.
    # Il secondo % 10 serve quando la somma è già multipla di 10:
    # (10 - 0) % 10 = 0, non 10.
    check_atteso = (10 - somma % 10) % 10
    check_trovato = int(pulito[10])

    if check_atteso != check_trovato:
        return False, (
            f"check digit errato: atteso {check_atteso}, "
            f"trovato {check_trovato} ('{value}')"
        )

    return True, None


def valida_importo(value: str) -> tuple[bool, str | None]:
    """Verifica un importo in formato italiano (1.234,56)."""

    if not value or not value.strip():
        return False, "campo vuoto"

    # --- NORMALIZZAZIONE: qui sta tutto il rischio ---
    pulito = value.strip()

    for simbolo in ["€", "EUR", "eur", " "]:
        pulito = pulito.replace(simbolo, "")

    # IL PUNTO CRUCIALE.
    # In italiano: punto = migliaia, virgola = decimali.
    # Decimal("1.234") leggerebbe "uno virgola 234" SENZA sollevare errori:
    # sbaglieresti di un fattore 1000 in silenzio.
    # Quindi: togli i punti, poi trasforma la virgola in punto.
    pulito = pulito.replace(".", "").replace(",", ".")

    # --- CONVERSIONE ---
    # Decimal, mai float: float(0.1) + float(0.2) != 0.3. Sui soldi non si fa.
    try:
        importo = Decimal(pulito)
    except InvalidOperation:
        return False, f"importo non parsabile: '{value}'"

    # --- GUARDIE SEMANTICHE ---
    # Decimal accetta "NaN" e "Infinity" senza protestare. Vanno esclusi a mano.
    if not importo.is_finite():
        return False, f"importo non finito: '{value}'"

    if importo < 0:
        return False, f"importo negativo: '{value}'"

    return True, None


def valida_data(value: str) -> tuple[bool, str | None]:
    """Verifica che value sia una data parsabile in un formato noto."""

    if not value or not value.strip():
        return False, "campo vuoto"

    pulito = value.strip()

    # Prova ogni formato: il primo che passa vince.
    for fmt in FORMATI_DATA:
        try:
            datetime.strptime(pulito, fmt)
            return True, None
        except ValueError:
            continue  # questo formato no, prova il prossimo

    return False, f"data non parsabile: '{pulito}' (attesi: {', '.join(FORMATI_DATA)})"

def parse_importo(value: str) -> Decimal | None:
    """Estrae il Decimal da un importo italiano. None se non parsabile.

    Duplica la normalizzazione di valida_importo: quella dice SE è valido,
    questa restituisce QUANTO vale. Servono entrambe.
    """
    if not value or not value.strip():
        return None

    pulito = value.strip()
    for simbolo in ["€", "EUR", "eur", " "]:
        pulito = pulito.replace(simbolo, "")
    pulito = pulito.replace(".", "").replace(",", ".")

    try:
        importo = Decimal(pulito)
    except InvalidOperation:
        return None

    return importo if importo.is_finite() else None

def parse_importo(value: str) -> Decimal | None:
    """Estrae il Decimal da un importo italiano. None se non parsabile.

    Duplica la normalizzazione di valida_importo: quella dice SE è valido,
    questa restituisce QUANTO vale. Servono entrambe.
    """
    if not value or not value.strip():
        return None

    pulito = value.strip()
    for simbolo in ["€", "EUR", "eur", " "]:
        pulito = pulito.replace(simbolo, "")
    pulito = pulito.replace(".", "").replace(",", ".")

    try:
        importo = Decimal(pulito)
    except InvalidOperation:
        return None

    return importo if importo.is_finite() else None