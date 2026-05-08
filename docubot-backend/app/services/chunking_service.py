"""
DocuBot — Servicio de chunking semántico contractual.

Estrategia de segmentación (por prioridad):
  1. Título / sección
  2. Cláusula
  3. Numeral
  4. Párrafo
  5. Tabla
  6. Página
  7. Límite de tokens

Tamaños recomendados por tipo documental:
  - Contratos:              700-1.200 tokens  (overlap 120-180)
  - Adendas:                500-900  tokens   (overlap 100-150)
  - RFIs:                   documento completo si es corto
  - Actas:                  por acuerdo / tema
  - Especificaciones técn.: 800-1.500 tokens  (overlap 150-250)
  - XLSX:                   por hoja/tabla
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional


# ─────────────────────────────────────────────────────────────
# Configuración de tamaños por tipo documental
# ─────────────────────────────────────────────────────────────
CHUNK_CONFIG: dict[str, dict] = {
    "contract":               {"max_tokens": 1200, "min_tokens": 700,  "overlap": 150},
    "addendum":               {"max_tokens": 900,  "min_tokens": 500,  "overlap": 120},
    "rfi":                    {"max_tokens": 1500, "min_tokens": 50,   "overlap": 75},
    "transmittal":            {"max_tokens": 800,  "min_tokens": 100,  "overlap": 80},
    "meeting_minutes":        {"max_tokens": 700,  "min_tokens": 100,  "overlap": 80},
    "technical_specification":{"max_tokens": 1500, "min_tokens": 800,  "overlap": 200},
    "drawing":                {"max_tokens": 500,  "min_tokens": 50,   "overlap": 50},
    "schedule":               {"max_tokens": 600,  "min_tokens": 100,  "overlap": 60},
    "commercial_proposal":    {"max_tokens": 1000, "min_tokens": 400,  "overlap": 100},
    "technical_proposal":     {"max_tokens": 1200, "min_tokens": 500,  "overlap": 120},
    "purchase_order":         {"max_tokens": 700,  "min_tokens": 100,  "overlap": 70},
    "change_order":           {"max_tokens": 800,  "min_tokens": 200,  "overlap": 80},
    "claim":                  {"max_tokens": 1000, "min_tokens": 300,  "overlap": 100},
    "letter":                 {"max_tokens": 800,  "min_tokens": 100,  "overlap": 80},
    "report":                 {"max_tokens": 1200, "min_tokens": 400,  "overlap": 120},
    "other":                  {"max_tokens": 1000, "min_tokens": 200,  "overlap": 100},
}

DEFAULT_CONFIG = {"max_tokens": 1000, "min_tokens": 200, "overlap": 100}

# Aproximación: 1 token ≈ 4 caracteres en español
CHARS_PER_TOKEN = 4


# ─────────────────────────────────────────────────────────────
# Patrones de estructura documental contractual
# ─────────────────────────────────────────────────────────────

# Cláusulas: "CLÁUSULA 5", "Cláusula 5.2", "5.", "5.2", "5.2.1"
CLAUSE_RE = re.compile(
    r"^(?:cláusula|clausula|artículo|articulo|sección|seccion|capítulo|capitulo)?\s*"
    r"(\d{1,3}(?:\.\d{1,3}){0,3})\s*[.\-–—]?\s+",
    re.IGNORECASE | re.MULTILINE,
)

# Títulos en mayúsculas o con formato de encabezado
HEADING_RE = re.compile(
    r"^(?:[A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚÑ\s]{4,}|#{1,4}\s+\S+)",
    re.MULTILINE,
)

# Marcadores de tabla extraída
TABLE_RE = re.compile(r"\[TABLA\]|\[HOJA:", re.IGNORECASE)


@dataclass
class Chunk:
    chunk_index: int
    content: str
    section_title: Optional[str]
    paragraph_number: Optional[str]
    start_page: int
    end_page: int
    token_count: int
    source_reference: dict
    metadata: dict


class ChunkingService:
    """Servicio de chunking semántico orientado a documentos contractuales."""

    def chunk(
        self,
        pages_data: list[dict],
        document_type: str,
        metadata: dict,
    ) -> list[Chunk]:
        """
        Recibe las páginas extraídas y retorna una lista de chunks semánticos.

        Args:
            pages_data: Lista de dicts con keys: page_number, text, layout_metadata
            document_type: Tipo documental (define tamaño de chunk)
            metadata: Metadatos base del documento (tenant_id, project_id, etc.)
        """
        cfg = CHUNK_CONFIG.get(document_type, DEFAULT_CONFIG)
        max_chars = cfg["max_tokens"] * CHARS_PER_TOKEN
        overlap_chars = cfg["overlap"] * CHARS_PER_TOKEN

        # 1. Concatenar todo el texto con marcadores de página
        full_text, page_map = self._build_full_text(pages_data)

        # 2. Segmentar en bloques semánticos
        segments = self._segment_by_structure(full_text, document_type)

        # 3. Dividir segmentos que superen max_chars y aplicar overlap
        chunks = self._finalize_chunks(
            segments=segments,
            max_chars=max_chars,
            overlap_chars=overlap_chars,
            page_map=page_map,
            metadata=metadata,
            document_type=document_type,
        )

        return chunks

    # ──────────────────────────────────────────────────────────
    # Métodos internos
    # ──────────────────────────────────────────────────────────

    def _build_full_text(self, pages_data: list[dict]) -> tuple[str, dict]:
        """
        Construye texto completo con marcadores de página.
        Retorna (full_text, page_map) donde page_map mapea
        posición de carácter → número de página.
        """
        parts = []
        page_map: dict[int, int] = {}  # char_offset → page_number
        offset = 0

        for page in sorted(pages_data, key=lambda p: p["page_number"]):
            text = (page.get("text") or "").strip()
            if not text:
                continue
            marker = f"\n[PAGE:{page['page_number']}]\n"
            page_map[offset] = page["page_number"]
            parts.append(marker + text)
            offset += len(marker) + len(text)

        return "\n\n".join(parts), page_map

    def _segment_by_structure(
        self, full_text: str, document_type: str
    ) -> list[dict]:
        """
        Divide el texto en segmentos respetando la estructura documental.
        Cada segmento incluye: text, section_title, paragraph_number.
        """
        segments = []

        # Estrategia 1: Por cláusulas numeradas (contratos, adendas, specs)
        if document_type in (
            "contract", "addendum", "technical_specification",
            "commercial_proposal", "technical_proposal", "claim",
        ):
            segments = self._split_by_clauses(full_text)

        # Estrategia 2: Por encabezados (actas, informes, transmittals)
        elif document_type in ("meeting_minutes", "report", "transmittal", "letter"):
            segments = self._split_by_headings(full_text)

        # Estrategia 3: Por hojas/tablas (XLSX)
        elif document_type == "schedule":
            segments = self._split_by_tables(full_text)

        # Estrategia 4: Documento completo (RFIs cortos, órdenes de compra)
        elif document_type in ("rfi", "purchase_order", "change_order"):
            if len(full_text) < 6000:  # < 1.500 tokens ≈ documento corto
                segments = [{"text": full_text, "section_title": None, "paragraph_number": None}]
            else:
                segments = self._split_by_clauses(full_text) or self._split_by_paragraphs(full_text)

        # Estrategia fallback: por párrafos
        if not segments:
            segments = self._split_by_paragraphs(full_text)

        return segments

    def _split_by_clauses(self, text: str) -> list[dict]:
        """Divide por cláusulas numeradas tipo 5.2 o CLÁUSULA 5."""
        matches = list(CLAUSE_RE.finditer(text))
        if len(matches) < 2:
            return []

        segments = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            if len(content) > 50:
                segments.append({
                    "text": content,
                    "section_title": None,
                    "paragraph_number": match.group(1),
                })
        return segments

    def _split_by_headings(self, text: str) -> list[dict]:
        """Divide por encabezados en mayúsculas o formato markdown."""
        matches = list(HEADING_RE.finditer(text))
        if len(matches) < 2:
            return []

        segments = []
        for i, match in enumerate(matches):
            start = match.start()
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            content = text[start:end].strip()
            if len(content) > 50:
                segments.append({
                    "text": content,
                    "section_title": match.group(0).strip()[:200],
                    "paragraph_number": None,
                })
        return segments

    def _split_by_tables(self, text: str) -> list[dict]:
        """Divide por marcadores de tabla/hoja XLSX."""
        parts = TABLE_RE.split(text)
        return [
            {"text": p.strip(), "section_title": f"Sección {i+1}", "paragraph_number": None}
            for i, p in enumerate(parts)
            if p.strip()
        ]

    def _split_by_paragraphs(self, text: str) -> list[dict]:
        """División fallback: por doble salto de línea."""
        paragraphs = re.split(r"\n{2,}", text)
        return [
            {"text": p.strip(), "section_title": None, "paragraph_number": None}
            for p in paragraphs
            if len(p.strip()) > 100
        ]

    def _finalize_chunks(
        self,
        segments: list[dict],
        max_chars: int,
        overlap_chars: int,
        page_map: dict,
        metadata: dict,
        document_type: str,
    ) -> list[Chunk]:
        """
        Convierte segmentos en Chunks, dividiendo los que son demasiado largos
        y añadiendo overlap entre chunks contiguos.
        """
        raw_chunks: list[dict] = []

        for seg in segments:
            text = seg["text"]
            if len(text) <= max_chars:
                raw_chunks.append(seg)
            else:
                # Dividir por párrafos respetando max_chars
                sub_paragraphs = re.split(r"\n{1,2}", text)
                current = ""
                for para in sub_paragraphs:
                    if len(current) + len(para) + 1 <= max_chars:
                        current += ("\n" if current else "") + para
                    else:
                        if current:
                            raw_chunks.append({
                                "text": current.strip(),
                                "section_title": seg["section_title"],
                                "paragraph_number": seg["paragraph_number"],
                            })
                        current = para
                if current.strip():
                    raw_chunks.append({
                        "text": current.strip(),
                        "section_title": seg["section_title"],
                        "paragraph_number": seg["paragraph_number"],
                    })

        # Construir Chunk objects con overlap
        chunks: list[Chunk] = []
        for idx, raw in enumerate(raw_chunks):
            content = raw["text"]

            # Agregar overlap del chunk anterior
            if idx > 0 and overlap_chars > 0:
                prev_text = raw_chunks[idx - 1]["text"]
                overlap_text = prev_text[-overlap_chars:].strip()
                if overlap_text:
                    content = overlap_text + "\n\n" + content

            # Estimar página
            page_num = self._estimate_page(content, page_map)

            token_count = len(content) // CHARS_PER_TOKEN

            source_ref = {
                "document": metadata.get("document_title", ""),
                "revision": metadata.get("revision_number", ""),
                "page_start": page_num,
                "page_end": page_num,
                "section": raw.get("section_title"),
                "paragraph": raw.get("paragraph_number"),
            }

            chunk_meta = {
                "tenant_id": metadata.get("tenant_id"),
                "project_id": metadata.get("project_id"),
                "document_id": metadata.get("document_id"),
                "document_version_id": metadata.get("document_version_id"),
                "document_title": metadata.get("document_title"),
                "document_type": document_type,
                "revision_number": metadata.get("revision_number"),
                "discipline": metadata.get("discipline"),
                "source_path": metadata.get("blob_path"),
                "checksum_sha256": metadata.get("checksum_sha256"),
            }

            chunks.append(Chunk(
                chunk_index=idx,
                content=content,
                section_title=raw.get("section_title"),
                paragraph_number=raw.get("paragraph_number"),
                start_page=page_num,
                end_page=page_num,
                token_count=token_count,
                source_reference=source_ref,
                metadata=chunk_meta,
            ))

        return chunks

    def _estimate_page(self, text: str, page_map: dict) -> int:
        """Estima el número de página a partir del marcador [PAGE:N] en el texto."""
        match = re.search(r"\[PAGE:(\d+)\]", text)
        if match:
            return int(match.group(1))
        # Fallback: primera página del mapa
        if page_map:
            return list(page_map.values())[0]
        return 1


chunking_service = ChunkingService()
