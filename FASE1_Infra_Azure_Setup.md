# DocuBot — Infraestructura Azure: Guía de Configuración
## Fase 1 — Recursos Azure para MVP

**Proyecto:** DocuBot — Módulo 02 Aurenza IA  
**Fecha:** 2026-05-06  
**Stack:** FastAPI + React + PostgreSQL/pgvector + Azure OpenAI + Azure AD B2C

---

## 1. Convención de nombres

| Recurso | Patrón | Ejemplo |
|---|---|---|
| Resource Group | `rg-docubot-{env}` | `rg-docubot-dev` |
| App Service | `app-docubot-api-{env}` | `app-docubot-api-dev` |
| Static Web App | `swa-docubot-{env}` | `swa-docubot-dev` |
| PostgreSQL | `psql-docubot-{env}` | `psql-docubot-dev` |
| Blob Storage | `stdocubot{env}` | `stdocubotdev` |
| Key Vault | `kv-docubot-{env}` | `kv-docubot-dev` |
| Service Bus | `sb-docubot-{env}` | `sb-docubot-dev` |
| App Insights | `appi-docubot-{env}` | `appi-docubot-dev` |
| Document Intelligence | `di-docubot-{env}` | `di-docubot-dev` |
| OpenAI | `oai-docubot-{env}` | `oai-docubot-dev` |

**Entornos:** `dev` | `staging` | `prod`  
**Región recomendada:** `eastus2` (disponibilidad Azure OpenAI GPT-4o)

---

## 2. Resource Group

```bash
az group create \
  --name rg-docubot-dev \
  --location eastus2 \
  --tags project=docubot env=dev module=aurenza-ia
```

---

## 3. Azure Database for PostgreSQL Flexible Server

```bash
az postgres flexible-server create \
  --name psql-docubot-dev \
  --resource-group rg-docubot-dev \
  --location eastus2 \
  --admin-user docubotadmin \
  --admin-password "<SECRET_FROM_KV>" \
  --sku-name Standard_D2s_v3 \
  --tier GeneralPurpose \
  --storage-size 128 \
  --version 16 \
  --high-availability Disabled \
  --tags project=docubot env=dev

# Habilitar extensiones requeridas
az postgres flexible-server parameter set \
  --server-name psql-docubot-dev \
  --resource-group rg-docubot-dev \
  --name azure.extensions \
  --value "VECTOR,PG_TRGM,UUID-OSSP"

# Crear base de datos
az postgres flexible-server db create \
  --server-name psql-docubot-dev \
  --resource-group rg-docubot-dev \
  --database-name docubot
```

---

## 4. Azure Blob Storage

```bash
az storage account create \
  --name stdocubotdev \
  --resource-group rg-docubot-dev \
  --location eastus2 \
  --sku Standard_LRS \
  --kind StorageV2 \
  --allow-blob-public-access false \
  --min-tls-version TLS1_2 \
  --tags project=docubot env=dev

# Crear contenedor de documentos
az storage container create \
  --name documents \
  --account-name stdocubotdev \
  --auth-mode login

# Habilitar versionamiento
az storage account blob-service-properties update \
  --account-name stdocubotdev \
  --resource-group rg-docubot-dev \
  --enable-versioning true
```

**Estructura de paths en Blob:**
```
documents/
  {tenant_id}/
    {project_id}/
      {document_id}/
        {version_id}/
          original/
            {filename}
```

---

## 5. Azure Key Vault

```bash
az keyvault create \
  --name kv-docubot-dev \
  --resource-group rg-docubot-dev \
  --location eastus2 \
  --sku standard \
  --tags project=docubot env=dev

# Secrets a crear en Key Vault:
# db-connection-string
# azure-openai-api-key
# azure-openai-endpoint
# azure-blob-connection-string
# azure-document-intelligence-key
# azure-document-intelligence-endpoint
# azure-service-bus-connection-string
# azure-ad-b2c-client-secret
```

---

## 6. Azure Service Bus

```bash
az servicebus namespace create \
  --name sb-docubot-dev \
  --resource-group rg-docubot-dev \
  --location eastus2 \
  --sku Standard \
  --tags project=docubot env=dev

# Cola para procesamiento de documentos
az servicebus queue create \
  --name document-processing \
  --namespace-name sb-docubot-dev \
  --resource-group rg-docubot-dev \
  --max-size 1024 \
  --default-message-time-to-live P7D \
  --lock-duration PT5M \
  --max-delivery-count 3

# Cola para alertas
az servicebus queue create \
  --name alert-notifications \
  --namespace-name sb-docubot-dev \
  --resource-group rg-docubot-dev \
  --max-size 1024 \
  --default-message-time-to-live P1D
```

---

## 7. Azure Document Intelligence

```bash
az cognitiveservices account create \
  --name di-docubot-dev \
  --resource-group rg-docubot-dev \
  --kind FormRecognizer \
  --sku S0 \
  --location eastus2 \
  --yes \
  --tags project=docubot env=dev
```

---

## 8. Azure OpenAI

```bash
az cognitiveservices account create \
  --name oai-docubot-dev \
  --resource-group rg-docubot-dev \
  --kind OpenAI \
  --sku S0 \
  --location eastus2 \
  --yes \
  --tags project=docubot env=dev

# Desplegar modelos (desde Azure Portal o az cognitiveservices):
# Deployment 1: gpt-4o      → nombre: gpt-4o
# Deployment 2: text-embedding-3-large → nombre: text-embedding-3-large
```

---

## 9. Azure App Service (Backend FastAPI)

```bash
# Plan de App Service
az appservice plan create \
  --name plan-docubot-dev \
  --resource-group rg-docubot-dev \
  --is-linux \
  --sku B2 \
  --tags project=docubot env=dev

# App Service para API FastAPI
az webapp create \
  --name app-docubot-api-dev \
  --resource-group rg-docubot-dev \
  --plan plan-docubot-dev \
  --runtime "PYTHON:3.12" \
  --tags project=docubot env=dev

# Habilitar identidad administrada (para acceso a Key Vault)
az webapp identity assign \
  --name app-docubot-api-dev \
  --resource-group rg-docubot-dev
```

---

## 10. Azure Static Web Apps (Frontend React)

```bash
az staticwebapp create \
  --name swa-docubot-dev \
  --resource-group rg-docubot-dev \
  --location eastus2 \
  --sku Free \
  --tags project=docubot env=dev
```

---

## 11. Azure Application Insights + Monitor

```bash
# Log Analytics Workspace
az monitor log-analytics workspace create \
  --workspace-name law-docubot-dev \
  --resource-group rg-docubot-dev \
  --location eastus2 \
  --tags project=docubot env=dev

# Application Insights
az monitor app-insights component create \
  --app appi-docubot-dev \
  --location eastus2 \
  --resource-group rg-docubot-dev \
  --workspace law-docubot-dev \
  --tags project=docubot env=dev
```

---

## 12. Azure AD B2C

**Configuración manual en Azure Portal:**

1. Crear tenant Azure AD B2C separado (ej: `docubotdev.onmicrosoft.com`).
2. Registrar aplicación backend (API):
   - Nombre: `DocuBot API`
   - Tipo: Web API
   - Exponer API: scope `docubot.read`, `docubot.write`
3. Registrar aplicación frontend (SPA):
   - Nombre: `DocuBot Frontend`
   - Tipo: SPA (Single Page Application)
   - Redirect URIs: `http://localhost:3000`, `https://swa-docubot-dev.azurestaticapps.net`
4. Crear User Flow: `B2C_1_susi` (Sign up / Sign in)
   - Atributos a recolectar: email, nombre
   - Claims a retornar: email, nombre, objectId, tenant_id (custom attribute)
5. Crear Custom Attribute: `TenantId` (string) para multi-tenant

---

## 13. Variables de entorno — Backend FastAPI

Archivo `.env` (guardado en Azure Key Vault en producción):

```env
# Base de datos
DATABASE_URL=postgresql+asyncpg://docubotadmin:<password>@psql-docubot-dev.postgres.database.azure.com:5432/docubot?ssl=require

# Azure Blob Storage
AZURE_BLOB_CONNECTION_STRING=<from-keyvault>
AZURE_BLOB_CONTAINER_NAME=documents

# Azure OpenAI
AZURE_OPENAI_API_KEY=<from-keyvault>
AZURE_OPENAI_ENDPOINT=https://oai-docubot-dev.openai.azure.com/
AZURE_OPENAI_API_VERSION=2024-02-01
AZURE_OPENAI_DEPLOYMENT_GPT4O=gpt-4o
AZURE_OPENAI_DEPLOYMENT_EMBEDDINGS=text-embedding-3-large

# Azure Document Intelligence
AZURE_DOCUMENT_INTELLIGENCE_KEY=<from-keyvault>
AZURE_DOCUMENT_INTELLIGENCE_ENDPOINT=https://di-docubot-dev.cognitiveservices.azure.com/

# Azure Service Bus
AZURE_SERVICE_BUS_CONNECTION_STRING=<from-keyvault>
AZURE_SERVICE_BUS_QUEUE_INGESTION=document-processing
AZURE_SERVICE_BUS_QUEUE_ALERTS=alert-notifications

# Azure AD B2C
AZURE_AD_B2C_TENANT=docubotdev.onmicrosoft.com
AZURE_AD_B2C_CLIENT_ID=<app-client-id>
AZURE_AD_B2C_POLICY=B2C_1_susi

# Application Insights
APPLICATIONINSIGHTS_CONNECTION_STRING=<from-keyvault>

# Configuración general
ENVIRONMENT=development
MAX_FILE_SIZE_MB=50
MAX_PAGES_PER_DOCUMENT=1000
RAG_DEFAULT_TOP_K=8
```

---

## 14. Checklist de validación

| Recurso | Verificación |
|---|---|
| PostgreSQL | Conectar con psql y ejecutar `SELECT version()` + `CREATE EXTENSION vector` |
| pgvector | Ejecutar `CREATE TABLE test_emb (id serial, v vector(3072))` |
| Blob Storage | Subir archivo de prueba y leer con SDK |
| Azure OpenAI GPT-4o | Llamada de prueba con prompt simple |
| Azure OpenAI Embeddings | Generar embedding de texto corto, verificar dimensión 3072 |
| Document Intelligence | Analizar PDF de prueba, verificar extracción de texto |
| Service Bus | Enviar y recibir mensaje de prueba |
| App Service | Deploy de FastAPI mínimo, verificar `/health` |
| Azure AD B2C | Flujo de login completo desde frontend, verificar JWT |
| Key Vault | App Service accede a secrets via identidad administrada |
