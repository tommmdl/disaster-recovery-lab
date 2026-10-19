#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
exec bash scripts/k.sh port-forward --address 127.0.0.1 service/notes-api 8022:80
