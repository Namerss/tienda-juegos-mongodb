"""
Paso 1 · Inicializa el Replica Set "rs0" con topología PSA:
    nodo1 (27017)   -> miembro con datos
    nodo2 (27018)   -> miembro con datos
    arbitro (27019) -> solo vota, no guarda datos

Requisito: los tres mongod ya levantados con config/inicial/*.conf
(ver infra/iniciar-nodos.*).

Uso:  python scripts/00_init_replicaset.py
"""

import time

from pymongo import MongoClient
from pymongo.errors import OperationFailure

from config import NODOS, REPLICA_SET, get_client

CONFIG_RS = {
    "_id": REPLICA_SET,
    "members": [
        {"_id": 0, "host": NODOS["nodo1"], "priority": 2},  # preferido como primario
        {"_id": 1, "host": NODOS["nodo2"], "priority": 1},
        {"_id": 2, "host": NODOS["arbitro"], "arbiterOnly": True},
    ],
}


def main():
    # Conexión directa al nodo1: todavía no existe un Replica Set al que conectarse.
    nodo1 = MongoClient(NODOS["nodo1"], directConnection=True, serverSelectionTimeoutMS=5000)

    try:
        nodo1.admin.command("replSetGetStatus")
        print("El Replica Set ya estaba inicializado.")
    except OperationFailure as e:
        if e.code != 94:  # 94 = NotYetInitialized
            raise
        print("Inicializando Replica Set...")
        nodo1.admin.command("replSetInitiate", CONFIG_RS)

    # Esperar a que se elija el primer primario.
    for _ in range(30):
        if nodo1.admin.command("hello").get("isWritablePrimary"):
            break
        time.sleep(1)
    else:
        raise SystemExit("No se eligió primario en 30 s; revisá los logs en /logs.")

    # Write concern por defecto explícito para PSA.
    # Con un árbitro, si cae un nodo con datos solo queda UNO capaz de
    # confirmar escrituras: w:"majority" quedaría bloqueado. Fijamos w:1 como
    # default y pedimos "majority" solo donde la durabilidad es crítica
    # (las transacciones de compra, ver 03_transaccion_compra.py).
    client = get_client()
    client.admin.command(
        "setDefaultRWConcern", defaultWriteConcern={"w": 1}, defaultReadConcern={"level": "local"}
    )

    status = client.admin.command("replSetGetStatus")
    print(f"\nReplica Set '{status['set']}' operativo:")
    for m in status["members"]:
        print(f"  {m['name']:<18} {m['stateStr']:<10} salud={m['health']}")


if __name__ == "__main__":
    main()
