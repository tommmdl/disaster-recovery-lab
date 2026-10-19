#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
case "${1:-status}" in
 kit) python3 scripts/prepare.py kit ;;
 create-target) python3 scripts/prepare.py cluster ;;
 install-target) python3 scripts/target.py ;;
 status)
   bash scripts/k.sh get nodes
   bash scripts/k.sh get deploy,sts,pods,pvc
   bash scripts/k.sh -n velero get backupstoragelocations,backups,restores,podvolumerestores
   ;;
 down)
   test "$(cat .local/cluster-owned)" = devops-recovery || exit 1
   echo 'Deleting only the owned recovery cluster and its recovered local volumes. Source and S3 remain.'
   ../kubernetes-lab/.local/bin/kind delete cluster --name devops-recovery
   python3 -c 'from pathlib import Path;Path(".local/cluster-owned").unlink(missing_ok=True);Path(".local/kubeconfig").unlink(missing_ok=True)'
   ;;
 *) echo 'Use: bash scripts/lab.sh kit|create-target|install-target|status|down' >&2; exit 1 ;;
esac
