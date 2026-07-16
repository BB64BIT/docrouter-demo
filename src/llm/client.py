# src/llm/client.py
"""Client LLM: estrazione + logprob per campo.

Il problema centrale: llama.cpp restituisce una lista PIATTA di token.
Il tuo ExtractedField vuole un logprob PER CAMPO. In mezzo serve lo
span mapping: ricostruire il JSON dai token, trovare dove sta ogni
valore, e prendere solo i token che cadono in quello span.
"""

import json
import math
from typing import Protocol

import httpx


class LLMClient(Protocol):
    def extract(self, testo: str, campi: list[str]) -> tuple[dict[str, str], dict[str, float], str]:
        """Ritorna ({campo: valore}, {campo: mean_logprob}, raw_json)."""
        
        ...


def _media_geometrica(logprobs: list[float]) -> float:
    """exp(media dei logprob) — non media delle probabilità.

    Perché geometrica: una P.IVA con UNA cifra incerta è sbagliata.
    Non deve essere salvata dalle altre dieci cifre sicure.
      aritmetica: [0.22, 0.92, 0.92] → 0.69  (il debole si annega)
      geometrica: [0.22, 0.92, 0.92] → 0.55  (il debole pesa)
    Stesso principio dei gate: la catena vale quanto l'anello debole.
    """
    if not logprobs:
        return 0.0
    return math.exp(sum(logprobs) / len(logprobs))


def _trova_span_valore(raw: str, campo: str) -> tuple[int, int] | None:
    """Posizione (start, end) del VALORE di `campo` dentro la stringa JSON.

    Cerca '"campo"', poi i due apici del valore dopo i due punti.
    Ritorna gli offset di carattere del contenuto, apici esclusi.
    """
    chiave = f'"{campo}"'
    i = raw.find(chiave)
    if i == -1:
        return None

    # dai due punti in poi, il primo apice apre il valore
    j = raw.find(":", i + len(chiave))
    if j == -1:
        return None

    start = raw.find('"', j)
    if start == -1:
        return None
    start += 1  # dentro gli apici

    end = raw.find('"', start)
    if end == -1:
        return None

    return (start, end)


def _logprob_per_campo(
    raw: str,
    tokens: list[dict],
    campi: list[str],
) -> dict[str, float]:
    """LO SPAN MAPPING.

    I token non sanno a che campo appartengono. Ma sono in ordine:
    concatenandoli si ricostruisce `raw`. Tenendo il conto degli offset,
    ogni token sa DOVE sta. Incrociando con lo span del valore, sai
    quali token compongono quel campo.

    Senza questo, la media includerebbe graffe, virgole e nomi dei campi
    — tutti a ~0.99 perché struttura prevedibile — annacquando il segnale.
    """
    # offset di ogni token nella stringa ricostruita
    posizioni: list[tuple[int, int, float]] = []
    cursore = 0
    for t in tokens:
        testo_tok = t["token"]
        inizio = cursore
        cursore += len(testo_tok)
        posizioni.append((inizio, cursore, t["logprob"]))

    risultato: dict[str, float] = {}

    for campo in campi:
        span = _trova_span_valore(raw, campo)
        if span is None:
            risultato[campo] = 0.0
            continue

        v_start, v_end = span

        # un token conta se si SOVRAPPONE allo span (non se è contenuto:
        # un token può stare a cavallo del confine)
        lp = [
            logprob
            for (t_start, t_end, logprob) in posizioni
            if t_start < v_end and t_end > v_start
        ]

        risultato[campo] = _media_geometrica(lp)

    return risultato


class LlamaCppClient:
    """Client verso llama-server."""

    def __init__(self, base_url: str, timeout: float = 120.0, temperature: float = 0.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.temperature = temperature


    def __init__(self, base_url: str, timeout: float = 120.0, temperature: float = 0.0):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.temperature = temperature

    def extract(self, testo: str, campi: list[str]) -> tuple[dict[str, str], dict[str, float], str]:
        prompt = self._costruisci_prompt(testo, campi)

        # json_schema forza JSON valido per costruzione (via GBNF interna).
        # Il parsing non fallisce mai → gli offset sono affidabili.
        # NB: la grammatica rinormalizza le probabilità sui token ammessi:
        # l'incertezza carattere/cifra sparisce, quella cifra/cifra resta.
        # La prima la becca comunque valida_piva col check digit.
        schema = {
            "type": "object",
            "properties": {c: {"type": "string"} for c in campi},
            "required": campi,
        }

        payload = {
            "prompt": prompt,
            "n_predict": 512,
            "temperature": self.temperature,
            "n_probs": 1,          # ci serve solo il token scelto
            "json_schema": schema,
            "cache_prompt": True,  # riusa il KV del prompt di sistema
        }

        with httpx.Client(timeout=self.timeout) as c:
            r = c.post(f"{self.base_url}/completion", json=payload)
            r.raise_for_status()
            data = r.json()

        raw = data["content"]
        tokens = data.get("completion_probabilities", [])

        try:
            valori = json.loads(raw)
        except json.JSONDecodeError:
            # con json_schema non dovrebbe capitare, ma se il modello
            # viene troncato da n_predict sì.
            return {c: "" for c in campi}, {c: 0.0 for c in campi}, raw

        valori = {c: str(valori.get(c, "")) for c in campi}
        logprobs = _logprob_per_campo(raw, tokens, campi)

        return valori, logprobs, raw

    def _costruisci_prompt(self, testo: str, campi: list[str]) -> str:
        lista = "\n".join(f"- {c}" for c in campi)
        return f"""Estrai i seguenti campi dalla fattura. Copia i valori ESATTAMENTE come appaiono nel documento, senza riformattarli. Se un campo non è presente, usa stringa vuota.

Campi:
{lista}

Documento:
---
{testo}
---

JSON:"""


class MockLLMClient:
    """Risposte finte, deterministiche. Zero rete, zero GPU.

    Non è un ripiego: è come si testano pipeline e dashboard in 0.1s.
    E ti permette di preparare il CASO DI FALLIMENTO da mostrare in demo,
    invece di sperare che il modello vero allucini a comando.
    """
    def __init__(self, risposte: dict[str, str], logprobs: dict[str, float] | None = None):
        self.risposte = risposte
        self.logprobs = logprobs or {k: 0.95 for k in risposte}

    def extract(self, testo: str, campi: list[str]) -> tuple[dict[str, str], dict[str, float], str]:
        valori = {c: self.risposte.get(c, "") for c in campi}
        lp = {c: self.logprobs.get(c, 0.95) for c in campi}
        return valori, lp, json.dumps(valori, ensure_ascii=False)