"""
DocuBot — Fixtures pytest para tests unitarios y de integración.
"""
import asyncio
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import date, datetime, timedelta
from uuid import uuid4


# ── Event loop compartido para todos los tests async ──────────────────
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── Settings mockeados para no requerir .env en CI ────────────────────
@pytest.fixture(autouse=True, scope="session")
def mock_settings(tmp_path_factory):
    """Sobreescribe settings para no requerir conexiones Azure en tests unitarios."""
    with patch("app.core.config.settings") as mock_cfg:
        mock_cfg.DATABASE_URL = "postgresql+asyncpg://test:test@localhost/test"
        mock_cfg.OPENAI_API_KEY = "test-key"
        mock_cfg.OPENAI_MODEL_GPT4O = "gpt-4o"
        mock_cfg.OPENAI_MODEL_EMBEDDINGS = "text-embedding-3-large"
        mock_cfg.EMBEDDING_DIMENSIONS = 3072
        mock_cfg.STORAGE_LOCAL_PATH = "/tmp/docubot_test"
        mock_cfg.JWT_SECRET_KEY = "test-secret"
        mock_cfg.JWT_ALGORITHM = "HS256"
        mock_cfg.JWT_EXPIRE_MINUTES = 480
        mock_cfg.MAX_FILE_SIZE_MB = 50
        mock_cfg.MAX_PAGES_PER_DOCUMENT = 1000
        mock_cfg.RAG_DEFAULT_TOP_K = 8
        mock_cfg.RAG_MAX_TOP_K = 20
        mock_cfg.OCR_TIMEOUT_SECONDS = 30
        mock_cfg.GPT_TIMEOUT_SECONDS = 60
        mock_cfg.ALLOWED_ORIGINS = ["http://localhost:5173"]
        mock_cfg.DEBUG = True
        mock_cfg.ENVIRONMENT = "test"
        yield mock_cfg


# ── DB session mock ────────────────────────────────────────────────────
@pytest.fixture
def mock_db():
    db = AsyncMock()
    db.execute = AsyncMock()
    db.flush = AsyncMock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()
    db.add = MagicMock()
    return db


# ── Tenant y usuario de prueba ────────────────────────────────────────
TENANT_ID = str(uuid4())
USER_ID = str(uuid4())
PROJECT_ID = str(uuid4())
DOC_VERSION_ID = str(uuid4())


@pytest.fixture
def tenant_id():
    return TENANT_ID


@pytest.fixture
def project_id():
    return PROJECT_ID


@pytest.fixture
def doc_version_id():
    return DOC_VERSION_ID


@pytest.fixture
def current_user():
    user = MagicMock()
    user.tenant_id = TENANT_ID
    user.user_id = USER_ID
    user.email = "test@aurenza.cl"
    user.role = "project_manager"
    return user


# ── Páginas de documento de prueba ────────────────────────────────────
@pytest.fixture
def sample_pages():
    return [
        {"page_number": 1, "text": (
            "CONTRATO EPC A PRECIO FIJO\n"
            "CLÁUSULA 1. OBJETO DEL CONTRATO\n"
            "El presente contrato tiene por objeto la construcción de la Planta "
            "Concentradora de Cobre con capacidad de 15.000 t/día.\n\n"
            "CLÁUSULA 2. PRECIO\n"
            "El precio del contrato es de USD 42.500.000 (cuarenta y dos millones "
            "quinientos mil dólares americanos), a precio fijo.\n"
        )},
        {"page_number": 2, "text": (
            "CLÁUSULA 3. PLAZO\n"
            "El plazo de ejecución es de 24 meses contados desde la Orden de Proceder.\n\n"
            "CLÁUSULA 4. PENALIDADES\n"
            "En caso de retraso, el Contratista pagará una multa de 0,1% del precio del "
            "contrato por cada día de atraso, con un máximo de 10%.\n"
        )},
        {"page_number": 3, "text": (
            "CLÁUSULA 5. GARANTÍAS\n"
            "El Contratista deberá entregar las siguientes garantías:\n"
            "5.1 Boleta de fidelidad: 5% del precio del contrato.\n"
            "5.2 Boleta de correcta ejecución: 10% del precio del contrato.\n"
        )},
    ]


# ── OpenAI mock ───────────────────────────────────────────────────────
@pytest.fixture
def mock_openai_client():
    client = MagicMock()

    # Mock de completions
    completion = MagicMock()
    completion.choices = [MagicMock()]
    completion.choices[0].message.content = """{
        "answer": "El precio del contrato es USD 42.500.000 a precio fijo.",
        "interpretation": "Contrato EPC con precio fijo sin reajuste.",
        "risks_or_warnings": ["Verificar si incluye reajuste por IPC"],
        "confidence": 0.92,
        "requires_human_review": false,
        "evidence": [
            {
                "chunk_id": "chunk-001",
                "text": "El precio del contrato es de USD 42.500.000",
                "document_title": "Contrato EPC-2023-001",
                "page_number": 1,
                "relevance_score": 0.95
            }
        ]
    }"""
    client.chat.completions.create = AsyncMock(return_value=completion)

    # Mock de embeddings
    embed_response = MagicMock()
    embed_response.data = [MagicMock()]
    embed_response.data[0].embedding = [0.1] * 3072
    client.embeddings.create = AsyncMock(return_value=embed_response)

    return client
