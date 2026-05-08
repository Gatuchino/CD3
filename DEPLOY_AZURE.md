# DocuBot — Guía de Deploy a Azure

## Arquitectura de producción

```
Internet
   │
   ├── Azure Static Web Apps  ←  docubot-frontend (React)
   │         │
   │         └── API calls → Azure Container Apps (backend FastAPI)
   │                              │
   │              ┌───────────────┼───────────────────┐
   │              │               │                   │
   │         Azure DB        Azure Blob           Azure Service
   │         PostgreSQL       Storage              Bus (ingesta)
   │         (pgvector)       (PDFs)
   │
   └── Azure AD B2C  (autenticación usuarios)
```

---

## Paso 1 — Crear recursos Azure (una sola vez)

```bash
# Variables
RG="rg-docubot-prod"
LOCATION="eastus2"
ACR_NAME="acrdocubot"
POSTGRES_SERVER="docubot-db"
STORAGE_ACCOUNT="stdocubot"
SB_NAMESPACE="sb-docubot"
CONTAINER_ENV="docubot-env"
BACKEND_APP="docubot-backend"
STATIC_APP="docubot-frontend"

# Grupo de recursos
az group create --name $RG --location $LOCATION

# Azure Container Registry
az acr create \
  --resource-group $RG \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled true

# PostgreSQL Flexible Server
az postgres flexible-server create \
  --resource-group $RG \
  --name $POSTGRES_SERVER \
  --location $LOCATION \
  --admin-user docubot \
  --admin-password "<PASSWORD_SEGURO>" \
  --sku-name Standard_B2ms \
  --tier Burstable \
  --version 16 \
  --storage-size 32

# Instalar extensión pgvector
az postgres flexible-server execute \
  --resource-group $RG \
  --name $POSTGRES_SERVER \
  --database-name docubot \
  --querytext "CREATE EXTENSION IF NOT EXISTS vector;"

# Azure Blob Storage
az storage account create \
  --resource-group $RG \
  --name $STORAGE_ACCOUNT \
  --location $LOCATION \
  --sku Standard_LRS

az storage container create \
  --account-name $STORAGE_ACCOUNT \
  --name documents

# Azure Service Bus
az servicebus namespace create \
  --resource-group $RG \
  --name $SB_NAMESPACE \
  --location $LOCATION \
  --sku Basic

az servicebus queue create \
  --resource-group $RG \
  --namespace-name $SB_NAMESPACE \
  --name ingestion-queue
```

---

## Paso 2 — Azure Container Apps (backend)

```bash
# Crear entorno
az containerapp env create \
  --name $CONTAINER_ENV \
  --resource-group $RG \
  --location $LOCATION

# Obtener credenciales ACR
ACR_SERVER=$(az acr show --name $ACR_NAME --query loginServer -o tsv)
ACR_USER=$(az acr credential show --name $ACR_NAME --query username -o tsv)
ACR_PASS=$(az acr credential show --name $ACR_NAME --query passwords[0].value -o tsv)

# Crear Container App
az containerapp create \
  --name $BACKEND_APP \
  --resource-group $RG \
  --environment $CONTAINER_ENV \
  --image $ACR_SERVER/docubot-backend:latest \
  --registry-server $ACR_SERVER \
  --registry-username $ACR_USER \
  --registry-password $ACR_PASS \
  --target-port 8000 \
  --ingress external \
  --min-replicas 1 \
  --max-replicas 5 \
  --cpu 1.0 \
  --memory 2.0Gi \
  --env-vars \
    ENVIRONMENT=production \
    DATABASE_URL=secretref:database-url \
    AZURE_OPENAI_API_KEY=secretref:openai-api-key \
    AZURE_OPENAI_ENDPOINT=secretref:openai-endpoint \
    AZURE_BLOB_CONNECTION_STRING=secretref:blob-connection-string \
    AZURE_SERVICE_BUS_CONNECTION_STRING=secretref:servicebus-connection-string

# Obtener URL del backend
BACKEND_URL=$(az containerapp show \
  --name $BACKEND_APP \
  --resource-group $RG \
  --query properties.configuration.ingress.fqdn -o tsv)
echo "Backend URL: https://$BACKEND_URL"
```

---

## Paso 3 — Azure Static Web Apps (frontend)

```bash
# Crear Static Web App (conectado a GitHub)
az staticwebapp create \
  --name $STATIC_APP \
  --resource-group $RG \
  --source https://github.com/<TU_ORG>/docubot \
  --location "eastus2" \
  --branch main \
  --app-location "docubot-frontend" \
  --output-location "dist" \
  --login-with-github

# Configurar variables de entorno del frontend
az staticwebapp appsettings set \
  --name $STATIC_APP \
  --resource-group $RG \
  --setting-names \
    VITE_API_BASE_URL="https://$BACKEND_URL" \
    VITE_DEMO_MODE="false" \
    VITE_AZURE_CLIENT_ID="<CLIENT_ID_B2C>" \
    VITE_AZURE_AUTHORITY="https://<TENANT>.b2clogin.com/<TENANT>.onmicrosoft.com/B2C_1_signupsignin" \
    VITE_AZURE_REDIRECT_URI="https://<STATIC_APP_URL>"
```

---

## Paso 4 — Secrets de GitHub Actions

En tu repo GitHub → Settings → Secrets → Actions, crea:

| Secret | Descripción |
|--------|-------------|
| `AZURE_CREDENTIALS` | JSON del service principal (`az ad sp create-for-rbac`) |
| `ACR_LOGIN_SERVER` | Ej: `acrdocubot.azurecr.io` |
| `ACR_USERNAME` | Usuario del ACR |
| `ACR_PASSWORD` | Password del ACR |
| `AZURE_STATIC_WEB_APPS_API_TOKEN` | Token del Static Web App |
| `BACKEND_URL` | URL del Container App |
| `VITE_API_BASE_URL` | URL del backend para el build |
| `VITE_AZURE_CLIENT_ID` | Client ID de Azure AD B2C |
| `VITE_AZURE_AUTHORITY` | Authority URL de B2C |
| `VITE_AZURE_REDIRECT_URI` | URL de redirect (Static Web App) |

### Generar AZURE_CREDENTIALS:
```bash
az ad sp create-for-rbac \
  --name "docubot-github-actions" \
  --role contributor \
  --scopes /subscriptions/<SUB_ID>/resourceGroups/$RG \
  --sdk-auth
```

---

## Paso 5 — Primer deploy manual

```bash
# Build y push imagen inicial (antes de tener CI/CD)
cd docubot-backend

az acr login --name $ACR_NAME

docker build -f Dockerfile.prod -t $ACR_SERVER/docubot-backend:latest .
docker push $ACR_SERVER/docubot-backend:latest

# Actualizar Container App
az containerapp update \
  --name $BACKEND_APP \
  --resource-group $RG \
  --image $ACR_SERVER/docubot-backend:latest
```

---

## Paso 6 — Migraciones de BD

```bash
# Ejecutar migraciones al hacer deploy (desde local con VPN o desde un job)
DATABASE_URL="postgresql+asyncpg://docubot:<PASS>@$POSTGRES_SERVER.postgres.database.azure.com/docubot?ssl=require" \
  alembic upgrade head

# O aplicar schema directamente:
psql "host=$POSTGRES_SERVER.postgres.database.azure.com dbname=docubot user=docubot password=<PASS> sslmode=require" \
  -f FASE0_SQL_Schema_DocuBot.sql
```

---

## Flujo CI/CD resultante

```
git push main
    │
    ├── ci.yml         → Tests + lint (PR checks)
    ├── deploy-backend.yml → Build Docker → ACR → Container Apps
    └── deploy-frontend.yml → npm build → Azure Static Web Apps
```

Los PRs generan automáticamente un **staging environment** en Static Web Apps para revisión.

---

## Costos estimados (producción básica)

| Servicio | SKU | USD/mes aprox |
|----------|-----|--------------|
| Container Apps (backend) | 1 vCPU / 2GB | ~$30–50 |
| PostgreSQL Flexible | Standard_B2ms | ~$40 |
| Static Web Apps | Standard | $9 |
| Blob Storage | LRS, 100GB | ~$2 |
| Service Bus | Basic | <$1 |
| Container Registry | Basic | ~$5 |
| Azure OpenAI | pay-per-use | variable |
| **Total base** | | **~$90/mes** |
