"""Smoke test: estrazione + diagnostica logprob."""

import json

import httpx

from src.llm.client import LlamaCppClient
from src.pipeline import processa

POD_ID = "o6p1xv8192s8e0"
BASE_URL = f"https://{POD_ID}-8080.proxy.runpod.net"

TESTO = """FATTURA n. 2026/0042 del 15/07/2026

Eni S.p.A.
Piazzale Enrico Mattei 1, 00144 Roma
P.IVA IT 00743110157

Imponibile:        1.012,00 EUR
IVA 22%:             222,64 EUR
Totale documento:  1.234,64 EUR
"""

CAMPI = [
    "numero_fattura",
    "data_fattura",
    "piva_fornitore",
    "ragione_sociale_fornitore",
    "imponibile",
    "iva",
    "totale",
]



TESTO_SPORCO = """FATTURA n. 2O26/OO42 del l5/O7/2O26

Eni S.p.A.
P.IVA IT OO743IIO157

Imponibile:  1.O12,OO EUR
IVA 22%:       222,64 EUR
Totale:      1.234,64 EUR
"""

TESTO_SENZA_PIVA = """FATTURA n. 2026/0042 del 15/07/2026

Eni S.p.A.
Piazzale Enrico Mattei 1, 00144 Roma

Imponibile:        1.012,00 EUR
IVA 22%:             222,64 EUR
Totale documento:  1.234,64 EUR
"""


def test_ocr_sporco() -> None:
    """B guadagna il suo posto solo qui: O/0, l/1 — il fallimento 2."""
    print("\n--- OCR SPORCO ---")
    valori, logprobs, _ = client.extract(TESTO_SPORCO, CAMPI)
    for c in CAMPI:
        print(f"{c:28} = {valori[c]:24} logprob={logprobs[c]:.4f}")

def test_pipeline_reale() -> None:
    for nome, txt in [("PULITO", TESTO), ("OCR SPORCO", TESTO_SPORCO), ("SENZA P.IVA", TESTO_SENZA_PIVA)]:
        doc = processa(txt, client)
        print(f"\n--- {nome}: {doc.routing.upper()} ---")
        print(f"{doc.reason}")
        for f in doc.fields:
            stato = "OK" if f.routing == "auto" else "NO"
            print(f"  [{stato}] {f.name:26} = {f.value:24} conf={f.confidence:.2f} lp={f.mean_logprob:.3f}")
            if f.routing != "auto":
                print(f"       └─ {f.reason}")

def test_allucinazione() -> None:
    """La P.IVA NON è sul documento. Se la inventa?"""
    print("\n--- P.IVA ASSENTE ---")
    valori, logprobs, _ = client.extract(TESTO_SENZA_PIVA, CAMPI)
    v = valori["piva_fornitore"]
    print(f"piva_fornitore = '{v}'  logprob={logprobs['piva_fornitore']:.4f}")

    from src.core.validators import valida_piva
    from src.core.grounding import verifica_grounding

    ok, err = valida_piva(v)
    g = verifica_grounding(v, TESTO_SENZA_PIVA, "verbatim")
    print(f"  C  (valida_piva)  → {ok}  {err or ''}")
    print(f"  B  (logprob)      → {logprobs['piva_fornitore']:.4f}")
    print(f"  grounding         → {g}")

client_hot = LlamaCppClient(BASE_URL, temperature=0.7)


def test_temperatura() -> None:
    """temp=0 collassa la distribuzione: i logprob a 1.0 sono un artefatto del sampling?"""
    print("\n--- CONFRONTO TEMPERATURA (OCR sporco) ---")
    _, lp_freddo, _ = client.extract(TESTO_SPORCO, CAMPI)
    _, lp_caldo, _ = client_hot.extract(TESTO_SPORCO, CAMPI)

    print(f"{'campo':28} {'temp=0.0':>10} {'temp=0.7':>10}")
    for c in CAMPI:
        print(f"{c:28} {lp_freddo[c]:>10.4f} {lp_caldo[c]:>10.4f}")

client = LlamaCppClient(BASE_URL)


def estrazione() -> None:
    valori, logprobs, raw = client.extract(TESTO, CAMPI)
    print("\n--- RAW ---")
    print(raw)
    print("\n--- CAMPI ---")
    for campo in CAMPI:
        print(f"{campo:28} = {valori[campo]:24} logprob={logprobs[campo]:.4f}")


def diagnostica() -> None:
    """I logprob arrivano davvero, o leggo un artefatto?"""
    payload = {
        "prompt": client._costruisci_prompt(TESTO, CAMPI),
        "n_predict": 512,
        "temperature": 0.0,
        "n_probs": 1,
        "json_schema": {
            "type": "object",
            "properties": {c: {"type": "string"} for c in CAMPI},
            "required": CAMPI,
        },
    }
    r = httpx.post(f"{BASE_URL}/completion", json=payload, timeout=120).json()

    print("\n--- DIAGNOSTICA ---")
    print("chiavi risposta:", list(r.keys()))

    toks = r.get("completion_probabilities", [])
    print(f"token ricevuti: {len(toks)}")

    if toks:
        print(json.dumps(toks[:3], indent=2, ensure_ascii=False)[:900])
    else:
        print("!! completion_probabilities VUOTO — i logprob=1.0 sono un artefatto")



if __name__ == "__main__":
    test_pipeline_reale()

#if __name__ == "__main__":
 #   test_temperatura()

#if __name__ == "__main__":
   # estrazione()
   # diagnostica()
   # test_ocr_sporco()
   # test_allucinazione()