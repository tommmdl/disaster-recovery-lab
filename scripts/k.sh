#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
LAB=${KUBERNETES_LAB_DIR:-$ROOT/../kubernetes-lab}
exec "$LAB/.local/bin/kubectl" --kubeconfig "$ROOT/.local/kubeconfig" --context kind-devops-recovery --namespace dr-notes "$@"
