#!/usr/bin/env bash
# Levanta los 3 nodos del Replica Set (Linux / macOS).
# Uso: ./infra/iniciar-nodos.sh inicial   (Pasos 1 y 2)
#      ./infra/iniciar-nodos.sh seguro    (Paso 3)
set -euo pipefail
MODO="${1:-inicial}"
cd "$(dirname "$0")/.."
mkdir -p data/nodo1 data/nodo2 data/arbitro data/pids logs

for nodo in nodo1 nodo2 arbitro; do
  nohup mongod --config "config/$MODO/$nodo.conf" >/dev/null 2>&1 &
  echo $! > "data/pids/$nodo.pid"
  echo "$nodo iniciado en modo $MODO (PID $!)"
done
echo "Logs en ./logs — si un nodo no arranca, revisá su .log"
