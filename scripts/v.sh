#!/usr/bin/env bash
set -euo pipefail
ROOT=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
exec "$ROOT/.local/bin/velero" --kubeconfig "$ROOT/.local/kubeconfig" --kubecontext kind-devops-recovery --namespace velero "$@"
