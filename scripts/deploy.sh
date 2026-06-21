#!/usr/bin/env bash
# deploy.sh — Despliega el namespace apps (frontend + backend + postgres)
# Uso: ./scripts/deploy.sh
# Requiere: haber copiado secret.yaml.example → secret.yaml y completado valores

set -euo pipefail

K8S_DIR="$(cd "$(dirname "$0")/../k8s" && pwd)"

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

echo ""
echo "==> Esperando a que todos los pods estén listos..."
kubectl -n apps wait --for=condition=ready pod -l app=postgres --timeout=120s 2>/dev/null || true
kubectl -n apps wait --for=condition=ready pod -l app=backend  --timeout=120s 2>/dev/null || true
kubectl -n apps wait --for=condition=ready pod -l app=frontend --timeout=120s 2>/dev/null || true

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
echo "✅ Deploy de apps completado"