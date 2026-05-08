"""
DocuBot — Tests unitarios del servicio de chunking semántico.
Verifica: tamaños por tipo documental, detección de cláusulas,
segmentación por headings, overlap y casos extremos.
"""
import pytest
from app.services.chunking_service import (
    ChunkingService, CHUNK_CONFIG, DEFAULT_CONFIG, CHARS_PER_TOKEN
)


@pytest.fixture
def svc():
    return ChunkingService()


BASE_META = {"tenant_id": "t1", "project_id": "p1", "document_version_id": "v1"}


def pages(text: str, page_number: int = 1) -> list[dict]:
    """Helper: envuelve texto en el formato pages_data esperado."""
    return [{"page_number": page_number, "text": text, "layout_metadata": {}}]


def multipages(texts: list[str]) -> list[dict]:
    return [{"page_number": i + 1, "text": t, "layout_metadata": {}} for i, t in enumerate(texts)]


CONTRACT_TEXT = (
    "CLÁUSULA 1. OBJETO DEL CONTRATO\n"
    "El presente contrato tiene por objeto la construcción de la Planta Concentradora.\n\n"
    "CLÁUSULA 2. PRECIO\n"
    "El precio del contrato es de USD 42.500.000 a precio fijo.\n"
    "El pago se realizará en hitos mensuales según el programa de trabajo aprobado.\n\n"
    "CLÁUSULA 3. PLAZO\n"
    "El plazo de ejecución es de 24 meses contados desde la Orden de Proceder.\n\n"
    "CLÁUSULA 4. PENALIDADES\n"
    "En caso de retraso se aplicará una multa de 0,1% por día, con máximo de 10%.\n"
)

SHORT_TEXT = "Este es un documento muy corto."


# ── Configuración ─────────────────────────────────────────────────────
class TestChunkConfig:
    def test_all_doc_types_have_required_keys(self):
        for doc_type, cfg in CHUNK_CONFIG.items():
            assert "max_tokens" in cfg, f"{doc_type} falta max_tokens"
            assert "min_tokens" in cfg, f"{doc_type} falta min_tokens"
            assert "overlap" in cfg, f"{doc_type} falta overlap"

    def test_contract_has_large_chunks(self):
        assert CHUNK_CONFIG["contract"]["max_tokens"] >= 700

    def test_spec_allows_larger_chunks_than_contract(self):
        assert CHUNK_CONFIG["technical_specification"]["max_tokens"] >= CHUNK_CONFIG["contract"]["max_tokens"]

    def test_overlap_less_than_min_tokens(self):
        for doc_type, cfg in CHUNK_CONFIG.items():
            assert cfg["overlap"] < cfg["min_tokens"], (
                f"{doc_type}: overlap ({cfg['overlap']}) debe ser < min_tokens ({cfg['min_tokens']})"
            )


# ── ChunkingService ───────────────────────────────────────────────────
class TestChunkingService:
    def test_chunk_contract_returns_list(self, svc):
        result = svc.chunk(pages(CONTRACT_TEXT), document_type="contract", metadata=BASE_META)
        assert isinstance(result, list)
        assert len(result) > 0

    def test_chunks_have_required_fields(self, svc):
        result = svc.chunk(pages(CONTRACT_TEXT), document_type="contract", metadata=BASE_META)
        for chunk in result:
            assert hasattr(chunk, "chunk_index")
            assert hasattr(chunk, "content")
            assert chunk.content.strip() != ""

    def test_chunk_indices_are_sequential(self, svc):
        result = svc.chunk(pages(CONTRACT_TEXT), document_type="contract", metadata=BASE_META)
        for i, chunk in enumerate(result):
            assert chunk.chunk_index == i

    def test_no_chunk_exceeds_max_tokens(self, svc):
        max_chars = CHUNK_CONFIG["contract"]["max_tokens"] * CHARS_PER_TOKEN * 1.1
        result = svc.chunk(pages(CONTRACT_TEXT), document_type="contract", metadata=BASE_META)
        for chunk in result:
            assert len(chunk.content) <= max_chars, (
                f"Chunk {chunk.chunk_index} excede max_tokens: {len(chunk.content)} chars"
            )

    def test_short_text_produces_one_chunk(self, svc):
        result = svc.chunk(pages(SHORT_TEXT), document_type="letter", metadata=BASE_META)
        assert len(result) == 1
        assert SHORT_TEXT.strip() in result[0].content

    def test_unknown_doc_type_uses_default(self, svc):
        result = svc.chunk(pages(CONTRACT_TEXT), document_type="unknown_type_xyz", metadata=BASE_META)
        assert len(result) > 0

    def test_empty_text_returns_empty_or_single(self, svc):
        result = svc.chunk(pages(""), document_type="contract", metadata=BASE_META)
        assert result == [] or (len(result) == 1 and result[0].content.strip() == "")

    def test_multipage_assigns_page_numbers(self, svc):
        texts = [CONTRACT_TEXT[:200], CONTRACT_TEXT[200:]]
        result = svc.chunk(multipages(texts), document_type="contract", metadata=BASE_META)
        assert len(result) > 0
        pages_assigned = [c.start_page for c in result if c.start_page is not None]
        assert len(pages_assigned) > 0

    def test_all_text_covered_in_chunks(self, svc):
        """Cada línea significativa del texto original debe aparecer en algún chunk."""
        result = svc.chunk(pages(CONTRACT_TEXT), document_type="contract", metadata=BASE_META)
        all_content = " ".join(c.content for c in result)
        for line in CONTRACT_TEXT.splitlines():
            line = line.strip()
            if len(line) > 15:
                assert line[:25] in all_content, f"Línea no encontrada en chunks: '{line[:25]}'"
