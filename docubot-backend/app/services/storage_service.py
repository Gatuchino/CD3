"""
DocuBot — Servicio de almacenamiento local.
Reemplaza Azure Blob Storage con sistema de archivos local.
Compatible con Railway (volumen persistente en /data) y desarrollo local.
"""
import pathlib

from app.core.config import settings
from app.core.demo_mode import IS_DEMO

# Directorio base — en Railway configurar volumen en /data
STORAGE_ROOT = pathlib.Path(settings.STORAGE_LOCAL_PATH)
DEMO_STORAGE_ROOT = pathlib.Path("/tmp/docubot_uploads")


def _root() -> pathlib.Path:
    root = DEMO_STORAGE_ROOT if IS_DEMO else STORAGE_ROOT
    root.mkdir(parents=True, exist_ok=True)
    return root


class StorageService:
    """Gestión de archivos en disco local con API compatible con el resto del sistema."""

    async def upload_bytes(self, blob_path: str, data: bytes) -> str:
        """Guarda bytes en disco. Retorna ruta relativa como identificador."""
        dest = _root() / blob_path
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return blob_path

    async def download_bytes(self, blob_path: str) -> bytes:
        """Lee un archivo del disco."""
        dest = _root() / blob_path
        if not dest.exists():
            raise FileNotFoundError(f"Archivo no encontrado: {blob_path}")
        return dest.read_bytes()

    def generate_sas_url(self, blob_path: str, expiry_minutes: int = 30) -> str:
        """
        Retorna la ruta interna para descarga a través del endpoint
        GET /api/v1/files/{blob_path}.
        """
        return f"/api/v1/files/{blob_path}"

    async def delete_blob(self, blob_path: str) -> None:
        """Elimina un archivo del disco."""
        dest = _root() / blob_path
        if dest.exists():
            dest.unlink()

    def file_exists(self, blob_path: str) -> bool:
        return (_root() / blob_path).exists()


storage_service = StorageService()
