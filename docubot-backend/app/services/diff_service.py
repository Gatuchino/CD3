"""
DocuBot — Servicio de diff semantico entre versiones de documentos.
Usa GPT-4o para detectar cambios semanticos relevantes: obligaciones,
plazos, multas, responsabilidades, alcance y condiciones comerciales.
"""
import json
import re
import asyncio
from dataclasses import dataclass, field
from typing import Optional, List
from openai import OpenAI

from app.core.config import settings


# ─────────────────────────────────────────────────────────────
# Prompts
# ─────────────────────────────────────────────────────────────

DIFF_SYSTEM_PROMPT = """Eres un especialista en analisis contractual y control de cambios \
documentales para proyectos mineros, construccion y EPC/EPCM en Chile.

Tu tarea es comparar dos versiones de un documento y detectar todos los cambios \
semanticos relevantes, no solo diferencias textuales superficiales.

TIPOS DE CAMBIO A DETECTAR:
- obligation_changed     (cambio en obligaciones)
- deadline_changed       (cambio en plazos)
- penalty_added          (nueva multa o penalidad)
- penalty_removed        (eliminacion de multa)
- responsibility_changed (cambio de responsable)
- scope_changed          (cambio de alcance)
- technical_changed      (cambio en condicion tecnica)
- commercial_changed     (cambio en condicion comercial o de pago)
- risk_changed           (cambio en exposicion contractual)
- clause_added           (clausula nueva)
- clause_removed         (clausula eliminada)

NIVELES DE IMPACTO: low | medium | high | critical

REGLAS:
1. Se exhaustivo: busca cambios aunque esten expresados con palabras distintas.
2. Prioriza los cambios que afecten plazos, multas, responsabilidades y alcance.
3. Si un cambio puede generar una disputa o reclamo, marcalo como critical.
4. Activa requires_legal_review si hay cambios high o critical.
5. Si las versiones son identicas o no hay cambios relevantes, indica semantic_summary descriptivo y listas vacias.
6. Devuelve exclusivamente JSON valido.

FORMATO DE RESPUESTA:
{
  "semantic_summary": "Resumen ejecutivo de los cambios entre versiones.",
  "risk_level": "low|medium|high|critical",
  "critical_changes": [
    {
      "change_type": "",
      "previous_text": "",
      "new_text": "",
      "semantic_impact": "Descripcion del impacto contractual.",
      "risk_level": "",
      "recommended_action": "",
      "source_reference_previous": {"page": "", "paragraph": ""},
      "source_reference_new": {"page": "", "paragraph": ""}
    }
  ],
  "obligations_changed": [],
  "deadlines_changed": [],
  "commercial_impacts": [],
  "technical_impacts": [],
  "requires_legal_review": false
}"""

DIFF_HUMAN_TEMPLATE = """Compara las siguientes dos versiones del documento:

Documento: {document_title}
Proyecto: {project_name}

VERSION ANTERIOR ({previous_revision}):
{previous_version_text}

VERSION NUEVA ({new_revision}):
{new_version_text}

Instrucciones:
- Detecta cambios semanticos relevantes, no solo diferencias ortograficas.
- Prioriza cambios en plazos, obligaciones, multas y responsabilidades.
- Devuelve exclusivamente JSON valido."""


# ─────────────────────────────────────────────────────────────
# Dataclass de resultado
# ─────────────────────────────────────────────────────────────

@dataclass
class DiffResult:
    semantic_summary: str = ""
    risk_level: str = "low"
    critical_changes: List[dict] = field(default_factory=list)
    obligations_changed: List[dict] = field(default_factory=list)
    deadlines_changed: List[dict] = field(default_factory=list)
    commercial_impacts: List[dict] = field(default_factory=list)
    technical_impacts: List[dict] = field(default_factory=list)
    requires_legal_review: bool = False


# ─────────────────────────────────────────────────────────────
# Servicio
# ─────────────────────────────────────────────────────────────

# Palabras por version para el diff (primeras 2500 de cada version)
WORDS_PER_VERSION = 2500


class DiffService:
    def __init__(self):
        self._llm = OpenAI(api_key=settings.OPENAI_API_KEY)

    async def compare_versions(
        self,
        previous_pages: list[dict],
        new_pages: list[dict],
        document_title: str,
        project_name: str,
        previous_revision: str,
        new_revision: str,
    ) -> DiffResult:
        """
        Compara dos versiones de un documento con GPT-4o.
        Usa las primeras 2.500 palabras de cada version.
        """
        prev_text = self._extract_sample(previous_pages)
        new_text = self._extract_sample(new_pages)

        # Si ambas versiones son identicas, retornar sin llamar a la IA
        if prev_text.strip() == new_text.strip():
            return DiffResult(
                semantic_summary="Las dos versiones son identicas en contenido textual.",
                risk_level="low",
                requires_legal_review=False,
            )

        human_prompt = DIFF_HUMAN_TEMPLATE.format(
            document_title=document_title,
            project_name=project_name,
            previous_revision=previous_revision or "Rev. anterior",
            new_revision=new_revision or "Rev. nueva",
            previous_version_text=prev_text or "(sin texto extraido)",
            new_version_text=new_text or "(sin texto extraido)",
        )

        loop = asyncio.get_event_loop()

        def _call():
            response = self._llm.chat.completions.create(
                model=settings.OPENAI_MODEL_GPT4O,
                messages=[
                    {"role": "system", "content": DIFF_SYSTEM_PROMPT},
                    {"role": "user", "content": human_prompt},
                ],
                temperature=0.2,
                max_tokens=3000,
                response_format={"type": "json_object"},
                timeout=60,
            )
            return response.choices[0].message.content

        raw = await loop.run_in_executor(None, _call)
        return self._parse_result(raw)

    def _extract_sample(self, pages: list[dict]) -> str:
        """Extrae muestra de texto ordenada por numero de pagina."""
        full = "\n".join(
            p.get("text", "") for p in sorted(pages, key=lambda x: x.get("page_number", 0))
        )
        words = full.split()
        return " ".join(words[:WORDS_PER_VERSION])

    def _parse_result(self, raw: str) -> DiffResult:
        """Parsea JSON con fallback seguro."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    return DiffResult(
                        semantic_summary="Error al parsear la respuesta del modelo.",
                        risk_level="medium",
                        requires_legal_review=True,
                    )
            else:
                return DiffResult(
                    semantic_summary=raw[:500],
                    risk_level="medium",
                    requires_legal_review=True,
                )

        # Determinar risk_level general como el maximo entre cambios individuales
        risk_order = {"low": 0, "medium": 1, "high": 2, "critical": 3}
        risk_level = data.get("risk_level") or "low"

        # Verificar si hay cambios high/critical para forzar requires_legal_review
        all_changes = data.get("critical_changes") or []
        has_high_risk = any(
            risk_order.get(c.get("risk_level", "low"), 0) >= 2
            for c in all_changes
        )

        return DiffResult(
            semantic_summary=data.get("semantic_summary") or "",
            risk_level=risk_level,
            critical_changes=all_changes,
            obligations_changed=data.get("obligations_changed") or [],
            deadlines_changed=data.get("deadlines_changed") or [],
            commercial_impacts=data.get("commercial_impacts") or [],
            technical_impacts=data.get("technical_impacts") or [],
            requires_legal_review=bool(data.get("requires_legal_review", False)) or has_high_risk,
        )


diff_service = DiffService()
