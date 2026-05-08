"""
DocuBot — Servicio de resúmenes ejecutivos de contratos y documentos.
Usa GPT-4o para generar resúmenes orientados a la toma de decisiones,
adaptados a la audiencia: gerente de proyecto, contract manager, legal, auditor.
"""
import json
import re
import asyncio
from dataclasses import dataclass, field
from typing import Optional, List
from openai import OpenAI

from app.core.config import settings
from app.core.demo_mode import IS_DEMO, demo_summary


# ─────────────────────────────────────────────────────────────
# Prompts del sistema
# ─────────────────────────────────────────────────────────────

SUMMARY_SYSTEM_PROMPT = """Eres un experto en administracion contractual y gestion de proyectos \
de mineria y construccion en Chile. Tu tarea es generar resumenes ejecutivos precisos, concisos \
y orientados a la toma de decisiones.

AUDIENCIAS VALIDAS:
- gerente_proyecto   (foco en riesgos, hitos y exposicion)
- project_manager    (foco en compromisos, plazos y entregables)
- contract_manager   (foco en obligaciones, clausulas y penalidades)
- legal              (foco en riesgos legales, reclamos y disputas)
- auditor            (foco en trazabilidad y cumplimiento)

TIPOS DE RESUMEN:
- contractual   (analisis del contrato)
- technical     (analisis tecnico del documento)
- commercial    (analisis comercial y financiero)

REGLAS:
1. Adapta el nivel de detalle y vocabulario a la audiencia especificada.
2. El resumen debe ser accionable: que decisiones habilita esta informacion.
3. Se conciso: maximo 5 puntos por seccion.
4. No inventes datos. Si el documento no contiene informacion suficiente para
   una seccion, indica "No se encontro informacion suficiente".
5. Devuelve exclusivamente JSON valido.

FORMATO DE RESPUESTA:
{
  "executive_overview": "Parrafo breve que resume el documento en 3-4 oraciones.",
  "key_obligations": [
    "Obligacion clave 1.",
    "Obligacion clave 2."
  ],
  "critical_deadlines": [
    {
      "description": "Descripcion del plazo.",
      "deadline": "Fecha o plazo relativo.",
      "responsible": "Parte responsable."
    }
  ],
  "risks": [
    {
      "risk": "Descripcion del riesgo.",
      "impact": "Impacto potencial.",
      "severity": "low|medium|high|critical"
    }
  ],
  "commercial_conditions": [
    "Condicion comercial relevante."
  ],
  "recommended_actions": [
    "Accion recomendada 1."
  ]
}"""

SUMMARY_HUMAN_TEMPLATE = """Genera un resumen ejecutivo del siguiente documento:

Documento: {document_title} — {revision_number}
Proyecto: {project_name}
Tipo de resumen: {summary_type}
Audiencia: {audience}
Incluir riesgos: {include_risks}
Incluir plazos: {include_deadlines}
Incluir obligaciones: {include_obligations}

Contenido del documento:
{document_context}

Devuelve exclusivamente JSON valido."""


# ─────────────────────────────────────────────────────────────
# Dataclass de resultado
# ─────────────────────────────────────────────────────────────

@dataclass
class SummaryResult:
    executive_overview: str = ""
    key_obligations: List[str] = field(default_factory=list)
    critical_deadlines: List[dict] = field(default_factory=list)
    risks: List[dict] = field(default_factory=list)
    commercial_conditions: List[str] = field(default_factory=list)
    recommended_actions: List[str] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# Servicio
# ─────────────────────────────────────────────────────────────

# Palabras máximas del documento para el contexto del resumen
MAX_WORDS_SUMMARY = 5000

VALID_AUDIENCES = {
    "gerente_proyecto", "project_manager", "contract_manager",
    "legal", "auditor",
}
VALID_SUMMARY_TYPES = {"contractual", "technical", "commercial"}


class SummaryService:
    def __init__(self):
        self._llm = OpenAI(api_key=settings.OPENAI_API_KEY)

    async def generate(
        self,
        pages_data: list[dict],
        document_title: str,
        revision_number: str,
        project_name: str,
        audience: str = "project_manager",
        summary_type: str = "contractual",
        include_risks: bool = True,
        include_deadlines: bool = True,
        include_obligations: bool = True,
    ) -> SummaryResult:
        """
        Genera un resumen ejecutivo del documento con GPT-4o.
        Usa las primeras 5.000 palabras del texto completo.
        """
        # Validar y normalizar parámetros
        if audience not in VALID_AUDIENCES:
            audience = "project_manager"
        if summary_type not in VALID_SUMMARY_TYPES:
            summary_type = "contractual"

        # Construir contexto
        full_text = "\n".join(
            p.get("text", "") for p in sorted(pages_data, key=lambda x: x.get("page_number", 0))
        )
        words = full_text.split()
        document_context = " ".join(words[:MAX_WORDS_SUMMARY])

        if not document_context.strip():
            return SummaryResult(
                executive_overview="No se encontró texto extraído en el documento.",
                recommended_actions=["Verificar que el documento fue procesado correctamente."],
            )

        human_prompt = SUMMARY_HUMAN_TEMPLATE.format(
            document_title=document_title,
            revision_number=revision_number or "Revisión no especificada",
            project_name=project_name,
            summary_type=summary_type,
            audience=audience,
            include_risks="Sí" if include_risks else "No",
            include_deadlines="Sí" if include_deadlines else "No",
            include_obligations="Sí" if include_obligations else "No",
            document_context=document_context,
        )

        loop = asyncio.get_event_loop()

        def _call():
            response = self._llm.chat.completions.create(
                model=settings.OPENAI_MODEL_GPT4O,
                messages=[
                    {"role": "system", "content": SUMMARY_SYSTEM_PROMPT},
                    {"role": "user", "content": human_prompt},
                ],
                temperature=0.3,
                max_tokens=2500,
                response_format={"type": "json_object"},
                timeout=60,
            )
            return response.choices[0].message.content

        raw = await loop.run_in_executor(None, _call)
        return self._parse_result(raw)

    def _parse_result(self, raw: str) -> SummaryResult:
        """Parsea JSON con fallback seguro."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    return SummaryResult(executive_overview=raw[:500])
            else:
                return SummaryResult(executive_overview=raw[:500])

        return SummaryResult(
            executive_overview=data.get("executive_overview") or "",
            key_obligations=data.get("key_obligations") or [],
            critical_deadlines=data.get("critical_deadlines") or [],
            risks=data.get("risks") or [],
            commercial_conditions=data.get("commercial_conditions") or [],
            recommended_actions=data.get("recommended_actions") or [],
        )


summary_service = SummaryService()
