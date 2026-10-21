"""
Paso 1 · Monitor del Replica Set para capturar el failover.

Consulta cada segundo a los tres nodos por separado (comando "hello", que no
requiere autenticación) y muestra el rol de cada uno. Cuando algo cambia, lo
marca con ⚠, así queda registrado el momento exacto de la elección.

Al arrancar imprime los PID de cada mongod: es el número que hay que usar para
"matar" el primario.

Uso (en una terminal aparte, mientras corre 02_failover_insert_loop.py):
  python scripts/02b_monitor_replicaset.py
"""

import os
import time
from datetime import datetime

from pymongo import MongoClient
from pymongo.errors import PyMongoError

from config import NODOS

RAIZ = os.path.join(os.path.dirname(__file__), "..")


def rol(host):
    try:
        c = MongoClient(host, directConnection=True,
                        serverSelectionTimeoutMS=800, connectTimeoutMS=800)
        h = c.admin.command("hello")
        c.close()
        if h.get("isWritablePrimary"):
            return "PRIMARIO"
        if h.get("arbiterOnly"):
            return "ÁRBITRO"
        if h.get("secondary"):
            return "SECUNDARIO"
        return "INICIANDO"
    except PyMongoError:
        return "CAÍDO"


def pids():
    """Lee los PID que guardan los scripts de infra/ (data/pids/*.pid)."""
    salida = {}
    for nombre in NODOS:
        ruta = os.path.join(RAIZ, "data", "pids", f"{nombre}.pid")
        try:
            with open(ruta, encoding="utf-8-sig") as f:
                salida[nombre] = f.read().strip()
        except OSError:
            salida[nombre] = "?"
    return salida


def main():
    print("PID de cada proceso mongod:")
    for nombre, pid in pids().items():
        print(f"  {nombre:<8} {NODOS[nombre]:<16} PID {pid}")
    print("\nLinux/macOS:  kill -9 <PID>     Windows:  Stop-Process -Id <PID> -Force\n")

    encabezado = "  ".join(f"{n:<12}" for n in NODOS)
    print(f"{'hora':<10}  {encabezado}")
    anterior = None
    try:
        while True:
            estado = tuple(rol(h) for h in NODOS.values())
            marca = "  ⚠ CAMBIO" if anterior and estado != anterior else ""
            fila = "  ".join(f"{r:<12}" for r in estado)
            print(f"{datetime.now():%H:%M:%S}  {fila}{marca}")
            anterior = estado
            time.sleep(1)
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
