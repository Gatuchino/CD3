# DocuBot — Inicio Rápido Demo Local

## Requisito único
**Docker Desktop** instalado y corriendo.
Descarga: https://www.docker.com/products/docker-desktop/

---

## Levantar en 1 paso

Abre una terminal en esta carpeta y ejecuta:

```bash
# Windows (PowerShell)
./start-demo.sh

# O directamente con Docker Compose
docker compose up --build -d
```

Espera ~2 minutos la primera vez (descarga imágenes + build).

---

## URLs una vez levantado

| Servicio | URL |
|---|---|
| **Frontend (App)** | http://localhost:5173 |
| **Backend API** | http://localhost:8000 |
| **API Docs (Swagger)** | http://localhost:8000/docs |

El frontend no pide login en modo demo — entra directo.

---

## Datos de demo incluidos

- **Proyecto**: Planta Concentradora Norte
- **4 documentos**: Contrato EPC, Adenda N°2, Especificaciones, RFI-043
- **2 alertas**: 1 vencida, 1 próxima
- **RAG**: respuestas simuladas realistas sin consumir tokens Azure

---

## Comandos útiles

```bash
# Ver logs del backend
docker compose logs -f backend

# Detener todo
docker compose down

# Reiniciar limpio (borra BD)
docker compose down -v && docker compose up --build -d

# Cargar datos demo manualmente
docker compose exec backend python scripts/seed_demo.py
```

---

## Pasar a producción real

1. Copia `.env.demo` → `.env` y completa las keys Azure reales
2. Cambia `Dockerfile.demo` → `Dockerfile` en `docker-compose.yml`
3. Cambia `requirements.demo.txt` → `requirements.txt`
4. Configura Azure PostgreSQL, Blob Storage y OpenAI
5. Despliega en Azure App Service o AKS
