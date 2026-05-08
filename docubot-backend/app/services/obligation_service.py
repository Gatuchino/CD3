"""
DocuBot — Servicio de extracción de obligaciones, plazos y alertas.
Usa GPT-4o para identificar obligaciones contractuales, fechas de vencimiento,
penalidades y entregables críticos. Genera alertas automáticas.
"""
import json
import re
import asyncio
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Optional, List
from openai import OpenAI

from app.core.config import settings


# ─────────────────────────────────────────────────────────────
# Prompts del sistema
# ─────────────────────────────────────────────────────────────

OBLIGATION_SYSTEM_PROMPT = """Eres un experto en análisis de contratos EPC/EPCM y documentos \
contractuales para proyectos mineros e industriales en Chile.

Tu tarea es extraer del texto proporcionado:
1. OBLIGACIONES CONTRACTUALES: compromisos, responsabilidades, entregables y penalidades.
2. PLAZOS Y VENCIMIENTOS: fechas absolutas o relativas críticas para el proyecto.

TIPOS DE OBLIGACIONES VÁLIDOS:
entregable | pago | reporte | permiso | seguro | garantia | penalidad |
notificacion | aprobacion | inspeccion | capacitacion | otro

TIPOS DE PLAZOS VÁLIDOS:
inicio_obra | hito | entrega | pago | vencimiento_garantia | vencimiento_seguro |
plazo_reporte | plazo_rfi | penalidad | cierre | otro

REGLAS OBLIGATORIAS:
1. Extrae SOLO lo que está explícitamente en el texto. No inventes.
2. Para fechas relativas (ej: "5 días hábiles desde adjudicación"), usa due_date=null y llena relative_deadline.
3. Prioriza cláusulas con importancia contractual alta: penalidades, hitos, pagos, garantías.
4. Asigna confidence_score entre 0.0 y 1.0 por cada ítem.
5. Incluye source_reference con: document, revision, page (si disponible), paragraph, quote (cita textual exacta).
6. Si no encuentras obligaciones o plazos relevantes, devuelve listas vacías.
7. Devuelve exclusivamente JSON válido.

FORMATO DE RESPUESTA:
{
  "obligations": [
    {
      "obligation_type": "entregable",
      "obligation_text": "Descripción clara de la obligación.",
      "responsible_party": "Contratista / Mandante / Ambas",
      "consequence": "Penalidad o consecuencia en caso de incumplimiento (null si no aplica).",
      "source_reference": {
        "document": "Nombre del documento",
        "revision": "Rev.X",
        "page": "N",
        "paragraph": "Cláusula o sección",
        "quote": "Texto exacto del documento."
      },
      "confidence_score": 0.90
    }
  ],
  "deadlines": [
    {
      "deadline_type": "hito",
      "description": "Descripción del plazo.",
      "due_date": "YYYY-MM-DD o null",
      "relative_deadline": "5 días hábiles desde adjudicación o null",
      "responsible_party": "Contratista / Mandante",
      "source_reference": {
        "document": "Nombre del documento",
        "revision": "Rev.X",
        "page": "N",
        "paragraph": "Cláusula o sección",
        "quote": "Texto exacto del documento."
      },
      "confidence_score": 0.85
    }
  ]
}"""

OBLIGATION_HUMAN_TEMPLATE = """Extrae obligaciones contractuales y plazos del siguiente documento:

Nombre del archivo: {file_name}
Tipo de documento: {document_type}
Disciplina: {discipline}

Texto del documento (muestra de hasta 4.000 palabras):
{text_sample}

Devuelve exclusivamente JSON válido con las listas "obligations" y "deadlines"."""


# ─────────────────────────────────────────────────────────────
# Dataclasses de resultado
# ─────────────────────────────────────────────────────────────

@dataclass
class ObligationItem:
    obligation_type: str = "otro"
    obligation_text: str = ""
    responsible_party: Optional[str] = None
    consequence: Optional[str] = None
    source_reference: dict = field(default_factory=dict)
    confidence_score: float = 0.5


@dataclass
class DeadlineItem:
    deadline_type: str = "otro"
    description: str = ""
    due_date: Optional[str] = None          # ISO date string or None
    relative_deadline: Optional[str] = None
    responsible_party: Optional[str] = None
    source_reference: dict = field(default_factory=dict)
    confidence_score: float = 0.5


@dataclass
class ObligationExtractionResult:
    obligations: List[ObligationItem] = field(default_factory=list)
    deadlines: List[DeadlineItem] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────
# Servicio
# ─────────────────────────────────────────────────────────────

# Ventana de alerta: días de antelación según tipo y severidad
ALERT_LEAD_DAYS = {
    "vencimiento_garantia": 30,
    "vencimiento_seguro": 30,
    "pago": 15,
    "entrega": 15,
    "hito": 10,
    "penalidad": 7,
    "plazo_rfi": 5,
    "plazo_reporte": 5,
    "otro": 10,
}

ALERT_SEVERITY_MAP = {
    "vencimiento_garantia": "critical",
    "vencimiento_seguro": "critical",
    "penalidad": "critical",
    "pago": "high",
    "entrega": "high",
    "hito": "high",
    "plazo_rfi": "medium",
    "plazo_reporte": "medium",
    "otro": "low",
}


class ObligationService:
    def __init__(self):
        self._llm = OpenAI(api_key=settings.OPENAI_API_KEY)

    async def extract(
        self,
        pages_data: list[dict],
        file_name: str,
        document_type: str,
        discipline: str,
        version_id: str,
    ) -> ObligationExtractionResult:
        """
        Extrae obligaciones y plazos del documento con GPT-4o.
        Usa las primeras 4.000 palabras del texto.
        """
        full_text = "\n".join(
            p.get("text", "") for p in sorted(pages_data, key=lambda x: x["page_number"])
        )
        words = full_text.split()
        text_sample = " ".join(words[:4000])

        human_prompt = OBLIGATION_HUMAN_TEMPLATE.format(
            file_name=file_name,
            document_type=document_type,
            discipline=discipline,
            text_sample=text_sample or "(sin texto extraído)",
        )

        loop = asyncio.get_event_loop()

        def _call():
            response = self._llm.chat.completions.create(
                model=settings.OPENAI_MODEL_GPT4O,
                messages=[
                    {"role": "system", "content": OBLIGATION_SYSTEM_PROMPT},
                    {"role": "user", "content": human_prompt},
                ],
                temperature=0.0,
                max_tokens=2500,
                response_format={"type": "json_object"},
                timeout=45,
            )
            return response.choices[0].message.content

        raw = await loop.run_in_executor(None, _call)
        return self._parse_result(raw)

    def _parse_result(self, raw: str) -> ObligationExtractionResult:
        """Parsea JSON de respuesta con fallback seguro."""
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", raw, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(0))
                except json.JSONDecodeError:
                    return ObligationExtractionResult()
            else:
                return ObligationExtractionResult()

        obligations = []
        for item in data.get("obligations") or []:
            obligations.append(ObligationItem(
                obligation_type=item.get("obligation_type") or "otro",
                obligation_text=item.get("obligation_text") or "",
                responsible_party=item.get("responsible_party"),
                consequence=item.get("consequence"),
                source_reference=item.get("source_reference") or {},
                confidence_score=float(item.get("confidence_score") or 0.5),
            ))

        deadlines = []
        for item in data.get("deadlines") or []:
            deadlines.append(DeadlineItem(
                deadline_type=item.get("deadline_type") or "otro",
                description=item.get("description") or "",
                due_date=item.get("due_date"),
                relative_deadline=item.get("relative_deadline"),
                responsible_party=item.get("responsible_party"),
                source_reference=item.get("source_reference") or {},
                confidence_score=float(item.get("confidence_score") or 0.5),
            ))

        return ObligationExtractionResult(obligations=obligations, deadlines=deadlines)

    def compute_alert_for_deadline(
        self,
        deadline: DeadlineItem,
        project_id: str,
        document_version_id: str,
        document_title: str,
    ) -> Optional[dict]:
        """
        Genera un dict de Alert si el deadline tiene fecha y está próximo.
        Retorna None si no aplica (fecha pasada sin margen o sin due_date).
        """
        if not deadline.due_date:
            # Sin fecha absoluta → alerta informativa si hay plazo relativo
            if deadline.relative_deadline:
                return {
                    "project_id": project_id,
                    "alert_type": "deadline",
                    "severity": ALERT_SEVERITY_MAP.get(deadline.deadline_type, "low"),
                    "title": f"Plazo relativo: {deadline.description[:200]}",
                    "description": (
                        f"Documento: {document_title}\n"
                        f"Plazo: {deadline.relative_deadline}\n"
                        f"Responsable: {deadline.responsible_party or 'No especificado'}"
                    ),
                    "due_date": None,
                    "source_document_version_id": document_version_id,
                    "source_reference": deadline.source_reference,
                }
            return None

        try:
            due = date.fromisoformat(deadline.due_date)
        except ValueError:
            return None

        today = date.today()
        lead_days = ALERT_LEAD_DAYS.get(deadline.deadline_type, 10)
        alert_date = due - timedelta(days=lead_days)

        # Solo crear alerta si la fecha aún no venció o si vence pronto
        if due < today:
            # Fecha ya vencida — crear alerta crítica
            severity = "critical"
            title = f"[VENCIDO] {deadline.description[:180]}"
        elif today >= alert_date:
            severity = ALERT_SEVERITY_MAP.get(deadline.deadline_type, "medium")
            days_left = (due - today).days
            title = f"[{days_left}d] {deadline.description[:180]}"
        else:
            # Aún no es momento de alertar
            return None

        return {
            "project_id": project_id,
            "alert_type": "deadline",
            "severity": severity,
            "title": title,
            "description": (
                f"Documento: {document_title}\n"
                f"Vencimiento: {deadline.due_date}\n"
                f"Responsable: {deadline.responsible_party or 'No especificado'}\n"
                f"Tipo: {deadline.deadline_type}"
            ),
            "due_date": due,
            "source_document_version_id": document_version_id,
            "source_reference": deadline.source_reference,
        }


obligation_service = ObligationService()
