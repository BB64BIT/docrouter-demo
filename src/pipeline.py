# src/pipeline.py
"""Orchestrazione: testo grezzo → ExtractedDocument verificato.

  1. LLM estrae i valori           (llm/client.py)
  2. Per ogni campo, la FieldSpec dice COME verificarlo   (core/schema.py)
  3. C: validazione sintattica     (core/validators.py)
  4. Grounding: è sul documento?   (core/grounding.py)
  5. I gate producono il verdetto  (core/fields.py)
  6. Il documento controlla la coerenza fra campi  (core/document.py)
"""

import uuid

from src.core.document import ExtractedDocument
from src.core.fields import ExtractedField
from src.core.grounding import verifica_grounding
from src.core.schema import FATTURA_SPEC, FieldSpec
from src.llm.client import LLMClient


def processa(
    testo: str,
    client: LLMClient,
    spec: list[FieldSpec] = FATTURA_SPEC,
    doc_id: str | None = None,
) -> ExtractedDocument:
    """Il cuore. Ogni riga qui è una domanda che ti faranno."""

    campi = [s.name for s in spec]

    # --- 1. L'unico punto in cui parliamo col modello ---
    valori, logprobs, _raw = client.extract(testo, campi)

    fields: list[ExtractedField] = []

    for s in spec:
        value = valori.get(s.name, "")

        # --- 2. C: validazione. La spec dice SE e COME. ---
        # validator=None è legittimo: "ragione_sociale" non ha regole
        # sintattiche. Nessun validator = nessun motivo per bocciarlo.
        if s.validator is not None:
            is_valid, err = s.validator(value)
        else:
            is_valid, err = True, None

        # --- 3. Grounding. Il modo viene dalla spec, non si deduce. ---
        grounding = verifica_grounding(value, testo, s.grounding_mode)

        fields.append(
            ExtractedField(
                name=s.name,
                value=value,
                mean_logprob=logprobs.get(s.name, 0.0),  # diagnostica, non decide
                is_valid=is_valid,
                validation_error=err,
                grounding=grounding,
                grounding_mode=s.grounding_mode,
                fuzzy_threshold=s.fuzzy_threshold,
            )
        )

    # --- 4. Il livello documento: la coerenza fra campi ---
    return ExtractedDocument(
        doc_id=doc_id or str(uuid.uuid4())[:8],
        testo=testo,
        fields=fields,
    )