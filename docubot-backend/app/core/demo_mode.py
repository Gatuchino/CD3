"""
DocuBot — Modo Demo.
Cuando ENVIRONMENT=demo, todas las llamadas externas retornan
datos simulados realistas. Permite levantar la app sin credenciales Azure.
"""
import os
import random
import math
from typing import List, Optional

IS_DEMO = os.getenv("ENVIRONMENT", "development") == "demo"


# ── Embeddings simulados ──────────────────────────────────────────────────────

def demo_embedding(text: str, dim: int = 3072) -> List[float]:
    """Genera un vector determinista basado en el hash del texto."""
    seed = hash(text) % (2**32)
    random.seed(seed)
    vec = [random.gauss(0, 1) for _ in range(dim)]
    norm = math.sqrt(sum(x**2 for x in vec)) or 1.0
    return [x / norm for x in vec]


# ── Respuestas RAG simuladas ──────────────────────────────────────────────────

DEMO_RAG_RESPONSES = [
    {
        "answer": "Según la Cláusula 8.2 del Contrato EPC (Rev. 4), el plazo total de ejecución es de 24 meses contados desde la Orden de Proceder, incluyendo 30 días de holgura para contingencias climáticas incorporados por la Adenda N°2.",
        "evidence": [{"document": "Contrato EPC Principal", "revision": "Rev. 4", "page": "43", "paragraph": "Cláusula 8.2", "quote": "El plazo total de ejecución será de 24 meses contados desde la Orden de Proceder."}],
        "interpretation": "El plazo fue ampliado desde 18 a 24 meses mediante Adenda N°2 del 28 de marzo de 2025.",
        "risks_or_warnings": ["Multa por atraso del 0,1% del valor del contrato por día, con tope de 10%."],
        "confidence": 0.93,
        "requires_human_review": False,
    },
    {
        "answer": "La multa máxima aplicable por incumplimiento de plazo es del 10% del valor total del contrato, según Cláusula 22.1 incorporada en la Adenda N°2. Puede descontarse directamente de los estados de pago pendientes.",
        "evidence": [{"document": "Adenda N°2", "revision": "Rev. 1", "page": "4", "paragraph": "Cláusula 22.1", "quote": "La multa máxima aplicable será del 10% del valor total del Contrato."}],
        "interpretation": "La penalidad fue aumentada desde el 5% original al 10% mediante la Adenda N°2.",
        "risks_or_warnings": ["El descuento es directo desde estados de pago, sin notificación previa."],
        "confidence": 0.91,
        "requires_human_review": False,
    },
    {
        "answer": "El contrato exige una Póliza CAR (Construction All Risk) por el 100% del valor del contrato, con Aurenza Group como asegurado adicional. Adicionalmente se requiere seguro de Responsabilidad Civil mínimo USD 5.000.000.",
        "evidence": [{"document": "Contrato EPC Principal", "revision": "Rev. 4", "page": "56", "paragraph": "Cláusula 20.1", "quote": "El Contratista deberá contratar y mantener vigente una póliza CAR por el 100% del valor del contrato."}],
        "interpretation": "Los seguros deben mantenerse hasta la Recepción Definitiva de las Obras.",
        "risks_or_warnings": ["La póliza debe ser aprobada por el mandante antes del inicio de obras."],
        "confidence": 0.95,
        "requires_human_review": False,
    },
]

def demo_rag_response(question: str) -> dict:
    idx = hash(question) % len(DEMO_RAG_RESPONSES)
    resp = DEMO_RAG_RESPONSES[idx].copy()
    resp["latency_ms"] = random.randint(800, 2400)
    return resp


# ── Resúmenes simulados ───────────────────────────────────────────────────────

def demo_summary(document_title: str) -> dict:
    return {
        "summary": f"El documento '{document_title}' establece las condiciones generales y específicas del contrato EPC modalidad suma alzada para la construcción de la Planta Concentradora Norte. Los aspectos críticos son: plazo de 24 meses, monto de USD 48.5 millones, multa máxima del 10% y exigencia de póliza CAR.",
        "key_clauses": [
            {"clause": "8.2", "title": "Plazos de Ejecución", "summary": "24 meses desde Orden de Proceder.", "criticality": "high"},
            {"clause": "18.1", "title": "Forma de Pago", "summary": "Estados de pago mensuales por avance certificado.", "criticality": "medium"},
            {"clause": "22.1", "title": "Multas y Penalidades", "summary": "0.1%/día, tope 10% del contrato.", "criticality": "high"},
            {"clause": "20.1", "title": "Seguros", "summary": "CAR 100% + RC Civil USD 5M.", "criticality": "medium"},
        ],
        "risks": ["Multa potencial de USD 4.85M por incumplimiento de plazo.", "EDP Cláusula 12.3 vencido."],
        "confidence": 0.92,
        "requires_human_review": False,
    }


# ── Clasificación simulada ────────────────────────────────────────────────────

DEMO_CLASSIFICATIONS = {
    "contrato": ("contract", 0.95),
    "adenda": ("amendment", 0.93),
    "rfi": ("rfi", 0.91),
    "especificacion": ("technical_spec", 0.88),
    "plano": ("drawing", 0.90),
    "acta": ("minutes", 0.85),
    "transmittal": ("transmittal", 0.87),
    "informe": ("report", 0.83),
}

def demo_classify(filename: str, content_preview: str) -> dict:
    fname = filename.lower()
    for keyword, (doc_type, conf) in DEMO_CLASSIFICATIONS.items():
        if keyword in fname or keyword in content_preview.lower():
            return {"document_type": doc_type, "confidence": conf, "requires_review": conf < 0.88}
    return {"document_type": "other", "confidence": 0.60, "requires_review": True}


# ── Obligaciones simuladas ────────────────────────────────────────────────────

from datetime import datetime, timedelta

def demo_obligations() -> list:
    today = datetime.utcnow()
    return [
        {"title": "Entrega Engineering Design Package", "clause": "12.3", "due_date": (today - timedelta(days=9)).isoformat(), "type": "deliverable", "status": "overdue", "confidence": 0.96},
        {"title": "Pago Estado N°4 — Avance 60%", "clause": "18.1", "due_date": (today + timedelta(days=8)).isoformat(), "type": "payment", "status": "upcoming", "confidence": 0.91},
        {"title": "Informe Mensual de Avance — Mayo", "clause": "14.2", "due_date": (today + timedelta(days=24)).isoformat(), "type": "report", "status": "pending", "confidence": 0.88},
        {"title": "Hito 3 — Inicio Montaje Estructural", "clause": "8.2.3", "due_date": (today + timedelta(days=44)).isoformat(), "type": "milestone", "status": "pending", "confidence": 0.76},
    ]
