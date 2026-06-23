#!/usr/bin/env bash
# build-push.sh — Build y push de imágenes Docker de EduTokens-app a Artifact Registry
# Uso: ./scripts/build-push.sh
# Requiere: gcloud auth configure-docker us-central1-docker.pkg.dev ejecutado antes
#
# Pushea cada imagen con dos tags:
#   :latest  — mutable, siempre apunta a la última versión
#   :${SHA}  — inmutable, trazable al commit exacto (igual que el CI)

set -euo pipefail

REGISTRY="us-central1-docker.pkg.dev/edutokens-2026/edutokens-repo"
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"

SHA=$(git -C "$APP_DIR" rev-parse --short=7 HEAD)
echo "==> Commit: $SHA"

echo "==> Autenticando contra Artifact Registry..."
gcloud auth configure-docker us-central1-docker.pkg.dev --quiet

echo ""
echo "==> Build EduTokens Backend..."
docker build -f "$APP_DIR/backend/Dockerfile" \
  -t "$REGISTRY/edutokens-backend:$SHA" \
  -t "$REGISTRY/edutokens-backend:latest" \
  "$APP_DIR/backend"

echo "==> Build EduTokens Frontend..."
docker build -f "$APP_DIR/frontend/Dockerfile" \
  -t "$REGISTRY/edutokens-frontend:$SHA" \
  -t "$REGISTRY/edutokens-frontend:latest" \
  "$APP_DIR/frontend"

echo ""
echo "==> Push EduTokens Backend ($SHA + latest)..."
docker push "$REGISTRY/edutokens-backend:$SHA"
docker push "$REGISTRY/edutokens-backend:latest"

echo "==> Push EduTokens Frontend ($SHA + latest)..."
docker push "$REGISTRY/edutokens-frontend:$SHA"
docker push "$REGISTRY/edutokens-frontend:latest"

echo ""
echo "✅ Build y push completado"
echo "   $REGISTRY/edutokens-backend:$SHA"
echo "   $REGISTRY/edutokens-backend:latest"
echo "   $REGISTRY/edutokens-frontend:$SHA"
echo "   $REGISTRY/edutokens-frontend:latest"
