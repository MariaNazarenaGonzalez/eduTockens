#!/usr/bin/env bash
# deploy.sh — Despliega el namespace apps (frontend + backend + postgres)
# Uso: ./scripts/deploy.sh
# Requiere: haber copiado secret.yaml.example → secret.yaml y completado valores
#
# Despliega las imágenes pineadas al SHA del commit actual (inmutable),
# igual que el CI de GitHub Actions. Requiere que las imágenes :${SHA}
# ya existan en el registry (corré build-push.sh antes).

set -euo pipefail

K8S_DIR="$(cd "$(dirname "$0")/../k8s" && pwd)"
APP_DIR="$(cd "$K8S_DIR/.." && pwd)"
SHA=$(git -C "$APP_DIR" rev-parse --short=7 HEAD)
REGISTRY="us-central1-docker.pkg.dev/edutokens-2026/edutokens-repo"

echo "==> Deploy SHA: $SHA"

echo "==> 1/4 Namespace"
kubectl apply -f "$K8S_DIR/namespace.yaml"

echo "==> 2/4 ConfigMaps + Secrets"
kubectl apply -f "$K8S_DIR/postgres-init-configmap.yaml"
kubectl apply -f "$K8S_DIR/postgres-secret.yaml"
kubectl apply -f "$K8S_DIR/backend-configmap.yaml"
kubectl apply -f "$K8S_DIR/backend-secret.yaml"
kubectl apply -f "$K8S_DIR/frontend-configmap.yaml"

echo "==> 3/4 Services"
kubectl apply -f "$K8S_DIR/postgres-service.yaml"
kubectl apply -f "$K8S_DIR/backend-service.yaml"
kubectl apply -f "$K8S_DIR/frontend-service.yaml"

echo "==> 4/4 StatefulSets + Deployments"
# PostgreSQL primero (el backend depende de él)
kubectl apply -f "$K8S_DIR/postgres-statefulset.yaml"

echo "   Esperando a que PostgreSQL esté listo..."
kubectl -n apps wait --for=condition=ready pod -l app=postgres --timeout=120s 2>/dev/null || true

kubectl apply -f "$K8S_DIR/backend-deployment.yaml"
kubectl apply -f "$K8S_DIR/frontend-deployment.yaml"

# Pinear las imágenes al SHA del commit (inmutable, trazable)
echo ""
echo "==> Pineando imágenes al SHA $SHA..."
kubectl -n apps set image deploy/backend  backend="${REGISTRY}/edutokens-backend:${SHA}"
kubectl -n apps set image deploy/frontend frontend="${REGISTRY}/edutokens-frontend:${SHA}"

echo ""
echo "==> Esperando a que todos los pods estén listos..."
kubectl -n apps wait --for=condition=ready pod -l app=postgres --timeout=120s 2>/dev/null || true
kubectl -n apps rollout status deployment/backend  --timeout=120s
kubectl -n apps rollout status deployment/frontend --timeout=120s

echo ""
echo "==> Estado final"
kubectl get pods -n apps

echo ""
echo "==> Verificación rápida de endpoints"
echo "Backend health:"
kubectl -n apps exec deploy/backend -- curl -sf http://localhost:8000/health 2>/dev/null || echo "  ⚠️  Backend aún no responde"
echo ""
echo "Frontend health (via nginx):"
kubectl -n apps exec deploy/frontend -- curl -sf http://localhost:80/health 2>/dev/null || echo "  ⚠️  Frontend aún no listo"

echo ""
echo "✅ Deploy de apps completado — SHA: $SHA"