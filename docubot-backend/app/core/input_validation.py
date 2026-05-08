"""
DocuBot — Validadores de input centralizados.
Previene injection, path traversal y payloads maliciosos.
"""
import re
import uuid
from typing import Optional
from fastapi import HTTPException, status
from pydantic import field_validator, model_validator
import bleach


# ── Patrones de validación ─────────────────────────────────────────────

# UUID v4 estricto
UUID_RE = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$",
    re.IGNORECASE,
)

# Código de proyecto (ej. "MIN-2024-001")
PROJECT_CODE_RE = re.compile(r"^[A-Z0-9\-\_\.]{1,50}$", re.IGNORECASE)

# Nombre de archivo seguro (sin path traversal)
SAFE_FILENAME_RE = re.compile(r"^[A-Za-z0-9\-\_\. ]{1,255}$")

# Patrones de inyección SQL básica
SQL_INJECTION_PATTERNS = [
    r"(\b(SELECT|INSERT|UPDATE|DELETE|DROP|UNION|ALTER|EXEC|EXECUTE)\b)",
    r"(--|;|/\*|\*/|xp_|WAITFOR|BENCHMARK)",
    r"(\bOR\b\s+\d+\s*=\s*\d+)",
    r"('\s*(OR|AND)\s*')",
]
SQL_INJECTION_RE = re.compile("|".join(SQL_INJECTION_PATTERNS), re.IGNORECASE)

# Patrones de inyección de prompts (para inputs que van al LLM)
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(previous|above|all)\s+instructions",
    r"you\s+are\s+now\s+",
    r"act\s+as\s+",
    r"jailbreak",
    r"DAN\s+mode",
    r"system\s*:\s*you",
    r"<\|im_start\|>",
    r"\[INST\]",
]
PROMPT_INJECTION_RE = re.compile("|".join(PROMPT_INJECTION_PATTERNS), re.IGNORECASE)


# ── Funciones de validación ────────────────────────────────────────────

def validate_uuid(value: str, field_name: str = "id") -> str:
    """Valida que el string sea un UUID v4 válido."""
    if not value or not UUID_RE.match(value.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{field_name}' debe ser un UUID v4 válido.",
        )
    return value.strip().lower()


def validate_project_code(code: str) -> str:
    """Valida código de proyecto alfanumérico."""
    if not code or not PROJECT_CODE_RE.match(code):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Código de proyecto inválido. Solo se permiten letras, números, guiones y puntos (max 50 chars).",
        )
    return code.strip().upper()


def validate_filename(filename: str) -> str:
    """Valida nombre de archivo — previene path traversal."""
    if not filename:
        raise HTTPException(status_code=400, detail="Nombre de archivo requerido.")

    # Normalizar: eliminar rutas
    name = filename.replace("\\", "/").split("/")[-1].strip()

    if not name or ".." in name or name.startswith("."):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nombre de archivo inválido o intento de path traversal.",
        )

    if len(name) > 255:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nombre de archivo demasiado largo (máx 255 caracteres).",
        )

    return name


def validate_text_input(text: str, field_name: str = "texto", max_length: int = 5000) -> str:
    """
    Sanitiza texto de usuario:
    - Limita longitud
    - Strip HTML con bleach
    - Detecta SQL injection básica
    """
    if not text:
        return text

    if len(text) > max_length:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{field_name}' supera el máximo de {max_length} caracteres.",
        )

    # Sanitizar HTML
    clean = bleach.clean(text, tags=[], strip=True).strip()

    # Detectar SQL injection
    if SQL_INJECTION_RE.search(clean):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"'{field_name}' contiene patrones no permitidos.",
        )

    return clean


def validate_rag_question(question: str) -> str:
    """
    Valida y sanitiza pregunta para el motor RAG.
    Detecta prompt injection además de los patrones estándar.
    """
    clean = validate_text_input(question, "pregunta", max_length=2000)

    if PROMPT_INJECTION_RE.search(clean):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="La pregunta contiene patrones no permitidos.",
        )

    return clean


def validate_file_type(content_type: str, filename: str) -> str:
    """
    Valida que el tipo de archivo sea uno de los permitidos por DocuBot.
    Retorna la extensión normalizada.
    """
    ALLOWED = {
        "application/pdf": "pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
        "application/msword": "doc",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": "xlsx",
        "application/vnd.ms-excel": "xls",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": "pptx",
        "text/plain": "txt",
    }

    ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    mime_ok = content_type in ALLOWED
    ext_ok = ext in ALLOWED.values()

    if not mime_ok or not ext_ok:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=(
                f"Tipo de archivo no permitido: {content_type} (.{ext}). "
                "Se permiten: PDF, DOCX, DOC, XLSX, XLS, PPTX, TXT."
            ),
        )

    return ext


def validate_file_size(size_bytes: int, max_mb: int = 50) -> None:
    """Valida que el archivo no supere el tamaño máximo permitido."""
    max_bytes = max_mb * 1024 * 1024
    if size_bytes > max_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Archivo demasiado grande. Máximo permitido: {max_mb} MB.",
        )
