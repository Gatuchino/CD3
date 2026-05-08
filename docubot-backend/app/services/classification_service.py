"""
DocuBot — Servicio de clasificación automática de documentos.
Usa GPT-4o para clasificar tipo documental, disciplina, fase y extraer metadatos.
"""
import json
import re
import asyncio
from dataclasses import dataclass, field
from typing import Optional
from openai import OpenAI

from app.core.config import settings
from app.core.demo_mode import IS_DEMO, demo_classify

# ─────────────────────────────────────────────────────────────
# Prompt de clasificación
# ─────────────────────────────────────────────────────────────

CLASSIFICATION_SYSTEM_PROMPT = """Eres un clasificador documental experto en proyectos \
mineros, construcción industrial, contratos EPC y EPCM en Chile.

TIPOS DOCUMENTALES VÁLIDOS:
contract | addendum | rfi | transmittal | meeting_minutes | technical_specification |
drawing | schedule | commercial_proposal | technical_proposal | purchase_order |
change_order | claim | letter | report | other

DISCIPLINAS VÁLIDAS:
contractual | commercial | engineering | construction | procurement |
safety | environmental | quality | planning | operations | legal | other

FASES DE PROYECTO VÁLIDAS:
tender | award | mobilization | execution | commissioning | closeout | dispute | unknown

REGLAS:
1. No inventes datos. Si no puedes determinar un campo con certeza, usa null.
2. Asigna confidence_score entre 0.0 y 1.0.
3. Si confidence_score < 0.70, activa requires_human_validation: true.
4. Devuelve exclusivamente JSON válido.

FORMATO DE RESPUESTA:
{
  "document_type": "",
  "discipline": "",
  "project_phase": "",
  "detected_metadata": {
    "contract_name": null,
    "owner": null,
    "contractor": null,
    "contract_number": null,
    "document_code": null,
    "revision": null,
    "date": null,
    "subject": null,
    "mentioned_responsibles": []
  },
  "confidence_score": 0.0,
  "classification_reason": "Explicación breve.",
  "requires_human_validation": true
}"""

CLASSIFICATION_HUMAN_TEMPLATE = """Clasifica el siguiente documento:

Nombre del archivo: {file_name}
Texto extraído (muestra):
{text_sample}

Devuelve exclusivamente JSON válido."""


# ─────────────────────────────────────────────────────────────
# Dataclass de resultado
# ─────────────────────────────────────────────────────────────

@dataclass
class ClassificationResult:
    document_type: str = "other"
    discipline: str = "other"
    project_phase: str = "unknown"
    detected_metadata: dict = field(default_factory=dict)
    confidence_score: float = 0.5
    classification_reason: str = ""
    requires_human_validation: bool = True


# ─────────────────────────────────────────────────────────────
# Servicio
# ─────────────────────────────────────────────────────────────

class ClassificationService:
    def __init__(self):
        self._llm = OpenAI(api_key=settings.OPENAI_API_KEY)

    async def classify(
        self,
        pages_data: list[dict],
        file_name: str,
        version_id: str,
    ) -> ClassificationResult:
        """
        Clasifica un documento con GPT-4o.
        Usa las primeras 3.000 palabras para la clasificación.
        """
        # Construir muestra de texto (primeras 3.000 palabras)
        full_text = "\n".join(
            p.get("text", "") for p in sorted(pages_data, key=lambda x: x["page_number"])
        )
        words = full_text.split()
        text_sample = " ".join(words[:3000])

        human_prompt = CLASSIFICATION_HUMAN_TEMPLATE.format(
            file_name=file_name,
            text_sample=text_sample or "(sin texto extraído)",
        )

        loop = asyncio.get_event_loop()

        def _call():
            response = self._llm.chat.completions.create(
                model=settings.OPENAI_MODEL_GPT4O,
                messages=[
                    {"role": "system", "content": CLASSIFICATION_SYSTEM_PROMPT},
                    {"role": "user", "content": human_prompt},
                ],
                temperature=0.0,
                max_tokens=600,
                response_format={"type": "json_object"},
                timeout=30,
            )
            return response.choices[0].message.content

        raw = await loop.run_in_executor(None, _call)
        return self._parse_result(raw)

    def _parse_result(self, raw: str) -> ClassificationResult:
        """Parsea la respuesta JSON de GPT-4o con fallback seguro."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    return ClassificationResult()
            else:
                return ClassificationResult()

        return ClassificationResult(
            document_type=data.get("document_type") or "other",
            discipline=data.get("discipline") or "other",
            project_phase=data.get("project_phase") or "unknown",
            detected_metadata=data.get("detected_metadata") or {},
            confidence_score=float(data.get("confidence_score") or 0.5),
            classification_reason=data.get("classification_reason") or "",
            requires_human_validation=bool(data.get("requires_human_validation", True)),
        )


classification_service = ClassificationService()
