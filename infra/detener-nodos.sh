#!/usr/bin/env bash
# Detiene ordenadamente los 3 nodos (Linux / macOS).
cd "$(dirname "$0")/.."
for nodo in nodo1 nodo2 arbitro; do
  f="data/pids/$nodo.pid"
  [ -f "$f" ] && kill "$(cat "$f")" 2>/dev/null && echo "$nodo detenido" || true
  rm -f "$f"
done
