# DocuBot — Guía de Deploy: Netlify + Railway

Stack de producción simplificado, sin Azure. Costo estimado: **~$15–25 USD/mes**.

---

## Resumen de arquitectura

```
aurenza-group.netlify.app        ← Sitio corporativo Aurenza (ya existe)
docubot.aurenzagroup.cl          ← Subdominio DocuBot (mismo Netlify)
        │
        └── API calls HTTPS ──► docubot-api.up.railway.app
                                        │
                                        ├── PostgreSQL + pgvector (Railway plugin)
                                        ├── OpenAI API (gpt-4o + embeddings)
                                        └── Volumen /data (archivos subidos)
```

---

## PASO 1 — Crear repositorio GitHub

1. Ve a https://github.com/new
2. Nombre: `aurenza-docubot`  (o `aurenza-os` si quieres un mono-repo)
3. Privado ✓ → **Create repository**

Desde tu carpeta del proyecto (PowerShell):

```powershell
cd "C:\Users\HP\OneDrive\Documentos\Claude\Projects\Aurenza Doc IA"
git init
git add .
git commit -m "feat: DocuBot MVP inicial"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/aurenza-docubot.git
git push -u origin main
```

---

## PASO 2 — Deploy backend en Railway

### 2.1 Crear cuenta y proyecto

1. Ve a https://railway.app → **Login with GitHub**
2. **New Project** → **Deploy from GitHub repo**
3. Selecciona `aurenza-docubot` → Railway detecta el `railway.toml` en `docubot-backend/`

> Si el repo tiene subcarpetas, en Railway: Settings → Source → **Root Directory** = `docubot-backend`

### 2.2 Agregar PostgreSQL

En tu proyecto Railway:
1. **+ New** → **Database** → **PostgreSQL**
2. Railway crea la DB y expone `DATABASE_URL` automáticamente en las variables de entorno

### 2.3 Configurar variables de entorno

En Railway → tu servicio backend → **Variables**, agrega:

| Variable | Valor |
|---|---|
| `OPENAI_API_KEY` | sk-... (de https://platform.openai.com/api-keys) |
| `JWT_SECRET_KEY` | genera con: `python -c "import secrets; print(secrets.token_hex(32))"` |
| `STORAGE_LOCAL_PATH` | `/data/documents` |
| `ENVIRONMENT` | `production` |
| `ALLOWED_ORIGINS` | `["https://aurenza-group.netlify.app","https://docubot.aurenzagroup.cl"]` |

> `DATABASE_URL` Railway lo inyecta automáticamente desde el plugin PostgreSQL.

### 2.4 Crear volumen persistente

En Railway → tu servicio → **Volumes**:
- Mount path: `/data`
- Size: 10 GB (suficiente para empezar)

### 2.5 Verificar deploy

Railway build el Dockerfile.prod, ejecuta `alembic upgrade head` y arranca uvicorn.

Una vez desplegado, visita:
```
https://docubot-backend.up.railway.app/health      → {"status":"ok"}
https://docubot-backend.up.railway.app/docs        → Swagger UI
```

Copia la URL del servicio (ej: `https://docubot-api-production.up.railway.app`) — la necesitas en el paso 3.

---

## PASO 3 — Deploy frontend en Netlify

### 3.1 Conectar repo

1. Ve a https://app.netlify.com → **Add new site** → **Import from GitHub**
2. Selecciona `aurenza-docubot`
3. Netlify detecta el `netlify.toml` en `docubot-frontend/`

Configuración de build (Netlify la lee del netlify.toml, pero verifica):
- **Base directory**: `docubot-frontend`
- **Build command**: `npm run build`
- **Publish directory**: `docubot-frontend/dist`

### 3.2 Variables de entorno en Netlify

En Netlify → Site settings → **Environment variables**:

| Variable | Valor |
|---|---|
| `VITE_API_BASE_URL` | URL de tu servicio Railway (ej: `https://docubot-api-production.up.railway.app`) |
| `VITE_DEMO_MODE` | `false` |
| `VITE_AZURE_CLIENT_ID` | (dejar vacío por ahora — auth simplificada) |
| `VITE_AZURE_AUTHORITY` | (dejar vacío) |
| `VITE_AZURE_REDIRECT_URI` | `https://docubot.aurenzagroup.cl` |

### 3.3 Trigger deploy

```
Deploys → Trigger deploy → Deploy site
```

---

## PASO 4 — Configurar subdominio (opcional pero recomendado)

Para que DocuBot quede en `docubot.aurenzagroup.cl`:

1. Netlify → Domain settings → **Add custom domain**: `docubot.aurenzagroup.cl`
2. En tu DNS (donde tengas el dominio aurenzagroup.cl):
   - Tipo: `CNAME`
   - Nombre: `docubot`
   - Valor: `tu-site.netlify.app`
3. Netlify provisiona HTTPS automáticamente (Let's Encrypt)

---

## PASO 5 — Conectar DocuBot desde el sitio Aurenza

En el sitio `aurenza-group.netlify.app`, el botón o link del módulo DocuBot debe apuntar a:
```
https://docubot.aurenzagroup.cl
```
o mientras no tengas dominio propio:
```
https://tu-site-docubot.netlify.app
```

---

## Costos estimados

| Servicio | Plan | Costo/mes |
|---|---|---|
| Railway — backend | Hobby ($5 crédito incluido) | ~$5–10 |
| Railway — PostgreSQL | Incluido en Hobby | $0 |
| Railway — Volumen 10GB | ~$0.25/GB | ~$2.50 |
| Netlify — frontend | Free (100GB bandwidth) | $0 |
| OpenAI API | Pay per use (~100 consultas RAG/día) | ~$5–15 |
| **Total** | | **~$12–27/mes** |

---

## Comandos útiles post-deploy

```bash
# Ver logs del backend en Railway (desde CLI)
railway logs --service docubot-backend

# Ejecutar migraciones manualmente si es necesario
railway run --service docubot-backend alembic upgrade head

# Cargar datos demo
railway run --service docubot-backend python scripts/seed_demo.py
```

---

## Cuando el proyecto crezca → migrar a Azure

El backend está diseñado para migrar a Azure Container Apps sin cambios de código:
1. Restaurar las variables de entorno Azure en `config.py` (están en `DEPLOY_AZURE.md`)
2. Cambiar `OPENAI_API_KEY` por variables `AZURE_OPENAI_*`
3. El `Dockerfile.prod` es compatible con Azure Container Registry sin modificaciones
