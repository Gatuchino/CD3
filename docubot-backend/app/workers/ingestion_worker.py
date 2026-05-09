"""
DocuBot — Worker de ingesta documental.
Pipeline completo: OCR → parsing → clasificación → chunking → embeddings → alertas.

Sin Service Bus: se dispara directamente desde FastAPI BackgroundTasks
en el endpoint de upload (POST /api/v1/projects/{id}/documents/upload).
Compatible con Railway, Render y cualquier servidor sin messaging broker.
"""
import asyncio
import re
from datetime import datetime

from sqlalchemy import select

from app.core.config import settings
from app.db.session import AsyncSessionLocal
from app.db.models import (
    DocumentVersion, DocumentPage, DocumentChunk,
    ChunkEmbedding, AuditLog,
)
from app.services.parser_service import parser_service
from app.services.ocr_service import ocr_service
from app.services.storage_service import storage_service
from app.services.chunking_service import chunking_service
from app.services.embedding_service import embedding_service


async def process_document_version(
    version_id: str, tenant_id: str, project_id: str
):
    """Pipeline completo de procesamiento de una versión de documento."""
    async with AsyncSessionLocal() as db:
        try:
            await _set_status(db, version_id, "processing")
            await db.commit()

            # PASO 1: Recuperar metadatos de la versión
            result = await db.execute(
                select(DocumentVersion).where(DocumentVersion.id == version_id)
            )
            version = result.scalar_one_or_none()
            if not version:
                raise ValueError(f"Versión {version_id} no encontrada.")

            # PASO 2: Descargar archivo del storage local
            file_bytes = await storage_service.download_bytes(version.blob_path)
            file_type = version.file_type

            # PASO 3: Parsear / aplicar OCR
            parse_result = parser_service.parse(file_bytes, file_type)

            if parse_result.requires_ocr or file_type in ("png", "jpg", "jpeg", "tiff"):
                extraction = await ocr_service.extract_from_bytes(file_bytes, file_type)
                pages_data = [
                    {
                        "page_number": p.page_number,
                        "text": p.text,
                        "confidence": p.confidence,
                        "ocr_engine": p.ocr_engine,
                        "layout_metadata": p.layout_metadata or {},
                    }
                    for p in extraction.pages
                ]
            else:
                pages_data = [
                    {
                        "page_number": p.page_number,
                        "text": p.text,
                        "confidence": 1.0,
                        "ocr_engine": "native_text",
                        "layout_metadata": p.layout_metadata or {},
                    }
                    for p in parse_result.pages
                ]

            version.page_count = len(pages_data)

            # PASO 4: Guardar páginas
            page_id_map: dict[int, str] = {}
            for p in pages_data:
                if not (p.get("text") or "").strip():
                    continue
                page = DocumentPage(
                    document_version_id=version_id,
                    page_number=p["page_number"],
                    extracted_text=_normalize_text(p["text"]),
                    layout_metadata=p["layout_metadata"],
                    ocr_confidence=p["confidence"],
                    ocr_engine=p["ocr_engine"],
                )
                db.add(page)
                await db.flush()
                page_id_map[p["page_number"]] = page.id

            # PASO 5: Clasificación documental (GPT-4o)
            from app.services.classification_service import classification_service
            from app.db.models import DocumentClassification
            classification = await classification_service.classify(
                pages_data=pages_data,
                file_name=version.file_name,
                version_id=version_id,
            )
            document_type = classification.document_type or "other"

            db.add(DocumentClassification(
                document_version_id=version_id,
                document_type=classification.document_type,
                discipline=classification.discipline,
                project_phase=classification.project_phase,
                detected_metadata=classification.detected_metadata,
                confidence_score=classification.confidence_score,
                classification_reason=classification.classification_reason,
                requires_human_validation=classification.requires_human_validation,
            ))

            # PASO 6: Chunking semántico
            from app.db.models import Document
            doc_result = await db.execute(
                select(Document).where(Document.current_version_id == version_id)
            )
            document = doc_result.scalar_one_or_none()

            if document and classification.confidence_score >= 0.75:
                if not document.document_type:
                    document.document_type = classification.document_type
                if not document.discipline:
                    document.discipline = classification.discipline

            chunk_metadata = {
                "tenant_id": tenant_id,
                "project_id": project_id,
                "document_id": document.id if document else None,
                "document_version_id": version_id,
                "document_title": document.title if document else version.file_name,
                "revision_number": version.revision_number,
                "discipline": (
                    classification.discipline
                    if classification.discipline != "other"
                    else (document.discipline if document else None)
                ),
                "blob_path": version.blob_path,
                "checksum_sha256": version.checksum_sha256,
            }

            chunks = chunking_service.chunk(
                pages_data=pages_data,
                document_type=document_type,
                metadata=chunk_metadata,
            )

            # PASO 7: Guardar chunks
            chunk_objects = []
            for chunk in chunks:
                page_id = page_id_map.get(chunk.start_page)
                db_chunk = DocumentChunk(
                    document_version_id=version_id,
                    page_id=page_id,
                    chunk_index=chunk.chunk_index,
                    content=chunk.content,
                    section_title=chunk.section_title,
                    paragraph_number=chunk.paragraph_number,
                    start_page=chunk.start_page,
                    end_page=chunk.end_page,
                    token_count=chunk.token_count,
                    source_reference=chunk.source_reference,
                    chunk_metadata=chunk.metadata,
                )
                db.add(db_chunk)
                await db.flush()
                chunk_objects.append(db_chunk)

            # PASO 8: Generar embeddings en batch
            if chunk_objects:
                texts = [c.content for c in chunk_objects]
                embeddings = await embedding_service.embed_batch(texts, batch_size=16)
                for db_chunk, emb_vector in zip(chunk_objects, embeddings):
                    db.add(ChunkEmbedding(
                        chunk_id=db_chunk.id,
                        embedding=emb_vector,
                        embedding_model=settings.OPENAI_MODEL_EMBEDDINGS,
                    ))

            # PASO 9: Extracción de obligaciones, plazos y alertas
            from app.services.obligation_service import obligation_service
            from app.db.models import ExtractedObligation, ExtractedDeadline, Alert as AlertModel
            ob_result = await obligation_service.extract(
                pages_data=pages_data,
                file_name=version.file_name,
                document_type=document_type,
                discipline=classification.discipline or "other",
                version_id=version_id,
            )

            for ob in ob_result.obligations:
                if ob.obligation_text.strip():
                    db.add(ExtractedObligation(
                        project_id=project_id,
                        document_version_id=version_id,
                        obligation_type=ob.obligation_type,
                        obligation_text=ob.obligation_text,
                        responsible_party=ob.responsible_party,
                        consequence=ob.consequence,
                        source_reference=ob.source_reference,
                        confidence_score=ob.confidence_score,
                        requires_human_validation=ob.confidence_score < 0.75,
                    ))

            alerts_count = 0
            for dl in ob_result.deadlines:
                if dl.description.strip():
                    db.add(ExtractedDeadline(
                        project_id=project_id,
                        document_version_id=version_id,
                        deadline_type=dl.deadline_type,
                        description=dl.description,
                        due_date=dl.due_date,
                        relative_deadline=dl.relative_deadline,
                        responsible_party=dl.responsible_party,
                        source_reference=dl.source_reference,
                        confidence_score=dl.confidence_score,
                    ))
                    alert_data = obligation_service.compute_alert_for_deadline(
                        deadline=dl,
                        project_id=project_id,
                        document_version_id=version_id,
                        document_title=document.title if document else version.file_name,
                    )
                    if alert_data:
                        db.add(AlertModel(**alert_data))
                        alerts_count += 1

            # FINALIZAR
            version.processing_status = "processed"
            version.processed_at = datetime.utcnow()

            db.add(AuditLog(
                tenant_id=tenant_id,
                action="document_processed",
                entity_type="document_version",
                entity_id=version_id,
                details={
                    "page_count": len(pages_data),
                    "chunk_count": len(chunk_objects),
                    "file_type": file_type,
                    "document_type": document_type,
                    "discipline": classification.discipline,
                    "project_phase": classification.project_phase,
                    "classification_confidence": classification.confidence_score,
                    "requires_human_validation": classification.requires_human_validation,
                    "obligations_extracted": len(ob_result.obligations),
                    "deadlines_extracted": len(ob_result.deadlines),
                    "alerts_generated": alerts_count,
                },
            ))
            await db.commit()

        except Exception as e:
            await _set_status(db, version_id, "error", error=str(e))
            await db.commit()
            raise


async def _set_status(db, version_id: str, status: str, error: str = None):
    result = await db.execute(
        select(DocumentVersion).where(DocumentVersion.id == version_id)
    )
    version = result.scalar_one_or_none()
    if version:
        version.processing_status = status
        if error:
            version.processing_error = error[:2000]


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = re.sub(r" {2,}", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
