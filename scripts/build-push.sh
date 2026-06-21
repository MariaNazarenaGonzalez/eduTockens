#!/usr/bin/env bash
# build-push.sh — Build y push de imágenes Docker de EduTokens-app a Artifact Registry
# Uso: ./scripts/build-push.sh
# Requiere: gcloud auth configure-docker us-central1-docker.pkg.dev ejecutado antes

set -euo pipefail

REGISTRY="us-central1-docker.pkg.dev/edutokens-2026/edutokens-repo"
APP_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "==> Autenticando contra Artifact Registry..."
gcloud auth configure-docker us-central1-docker.pkg.dev --quiet

echo ""
echo "==> Build EduTokens Backend..."
docker build -f "$APP_DIR/backend/Dockerfile" \
  -t "$REGISTRY/edutokens-backend:latest" \
  "$APP_DIR/backend"

echo "==> Build EduTokens Frontend..."
docker build -f "$APP_DIR/frontend/Dockerfile" \
  -t "$REGISTRY/edutokens-frontend:latest" \
  "$APP_DIR/frontend"

echo ""
echo "==> Push EduTokens Backend..."
docker push "$REGISTRY/edutokens-backend:latest"

echo "==> Push EduTokens Frontend..."
docker push "$REGISTRY/edutokens-frontend:latest"

echo ""
echo "✅ Build y push completado"
echo "   $REGISTRY/edutokens-backend:latest"
echo "   $REGISTRY/edutokens-frontend:latest"
