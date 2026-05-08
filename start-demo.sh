#!/bin/bash
# DocuBot — Levanta el entorno demo local completo
set -e

echo ""
echo "╔══════════════════════════════════════════════╗"
echo "║   DocuBot — Demo Local · Aurenza IA          ║"
echo "╚══════════════════════════════════════════════╝"
echo ""

# Verificar Docker
if ! command -v docker &>/dev/null; then
  echo "✗ Docker no encontrado. Instala Docker Desktop: https://www.docker.com/products/docker-desktop/"
  exit 1
fi

if ! docker compose version &>/dev/null; then
  echo "✗ Docker Compose no encontrado. Actualiza Docker Desktop."
  exit 1
fi

# Copiar env demo si no existe .env
if [ ! -f .env ]; then
  cp .env.demo .env
  echo "✓ .env creado desde .env.demo"
fi

# Copiar env demo al frontend
if [ ! -f docubot-frontend/.env ]; then
  cp docubot-frontend/.env.demo docubot-frontend/.env
  echo "✓ docubot-frontend/.env creado"
fi

echo ""
echo "▶ Construyendo imágenes Docker..."
docker compose build --quiet

echo ""
echo "▶ Iniciando servicios..."
docker compose up -d

echo ""
echo "▶ Esperando que la base de datos esté lista..."
sleep 8

echo ""
echo "▶ Cargando datos demo..."
docker compose exec backend python scripts/seed_demo.py || echo "  (seed omitido — BD ya tiene datos)"

echo ""
echo "═══════════════════════════════════════════════"
echo "✅ DocuBot está corriendo:"
echo ""
echo "   Frontend  →  http://localhost:5173"
echo "   Backend   →  http://localhost:8000"
echo "   API Docs  →  http://localhost:8000/docs"
echo ""
echo "   Para detener: docker compose down"
echo "═══════════════════════════════════════════════"
echo ""
