"""
Paso 1 · Prueba de resiliencia: inserta registros sin parar mientras
"matamos" el nodo primario.

Cada línea muestra qué nodo era el primario al momento de insertar. Cuando el
primario cae, las escrituras fallan unos segundos (la elección en curso) y
después continúan sobre el nuevo primario sin reiniciar el script.

Al cortar con Ctrl+C imprime un resumen: inserciones OK, tiempo sin primario
y verificación de que no se perdió ningún número de secuencia.

Uso:
  python scripts/02_failover_insert_loop.py              # corre el bucle
  python scripts/02_failover_insert_loop.py --verificar  # solo revisa huecos
"""

import sys
import time
from datetime import datetime, timezone

from pymongo.errors import AutoReconnect, DuplicateKeyError
from pymongo.write_concern import WriteConcern

from config import get_client, DB_NAME

INTERVALO_S = 0.2
COLECCION = "eventos_failover"


def ahora():
    return datetime.now().strftime("%H:%M:%S.%f")[:-3]


def primario_actual(client):
    p = client.primary  # (host, puerto) o None durante la elección
    return f"{p[0]}:{p[1]}" if p else "— sin primario —"


def verificar(col):
    """Busca números de secuencia faltantes (posibles escrituras revertidas)."""
    seqs = sorted(d["seq"] for d in col.find({}, {"seq": 1, "_id": 0}))
    if not seqs:
        print("No hay registros.")
        return
    faltantes = sorted(set(range(1, seqs[-1] + 1)) - set(seqs))
    print(f"Registros: {len(seqs)} · última secuencia: {seqs[-1]}")
    if faltantes:
        print(f"⚠ Faltan {len(faltantes)} secuencias: {faltantes[:20]}")
        print("  (escrituras con w:1 confirmadas por el primario caído que no llegaron")
        print("   a replicarse; MongoDB las guarda en la carpeta rollback/ del nodo)")
    else:
        print("✅ Sin huecos: ninguna escritura confirmada se perdió.")


def main():
    # Timeouts cortos para que la caída se note enseguida en pantalla.
    client = get_client(serverSelectionTimeoutMS=2000, connectTimeoutMS=2000)
    # w:1 -> confirma apenas el primario escribe. Con PSA y un nodo caído,
    # "majority" se quedaría esperando para siempre (ver README).
    col = client[DB_NAME].get_collection(COLECCION, write_concern=WriteConcern(w=1))

    if "--verificar" in sys.argv:
        verificar(col)
        return

    col.create_index("seq", unique=True)
    ultimo = col.find_one(sort=[("seq", -1)])
    seq = (ultimo["seq"] + 1) if ultimo else 1

    ok = errores = 0
    caida_desde = None
    caidas = []

    print("Insertando... matá el proceso del primario cuando quieras. Ctrl+C para terminar.\n")
    try:
        while True:
            try:
                col.insert_one({
                    "seq": seq,
                    "creado": datetime.now(timezone.utc),
                    "primario": primario_actual(client),
                })
                if caida_desde:
                    duracion = time.monotonic() - caida_desde
                    caidas.append(duracion)
                    print(f"[{ahora()}] ✅ Escrituras restablecidas tras {duracion:.1f} s")
                    caida_desde = None
                print(f"[{ahora()}] #{seq:05d} OK  → primario {primario_actual(client)}")
                ok += 1
                seq += 1
            except DuplicateKeyError:
                # El driver reintentó y la escritura ya había entrado: seguimos.
                seq += 1
            except AutoReconnect as e:
                # Incluye NotPrimaryError y ServerSelectionTimeoutError.
                errores += 1
                if not caida_desde:
                    caida_desde = time.monotonic()
                    print(f"[{ahora()}] ❌ PRIMARIO CAÍDO — esperando elección...")
                print(f"[{ahora()}]    reintentando #{seq:05d} ({type(e).__name__})")
                time.sleep(0.5)
                continue
            time.sleep(INTERVALO_S)
    except KeyboardInterrupt:
        pass

    print("\n──── Resumen ────")
    print(f"Inserciones OK:        {ok}")
    print(f"Intentos fallidos:     {errores}")
    for i, d in enumerate(caidas, 1):
        print(f"Indisponibilidad #{i}:   {d:.1f} s")
    verificar(col)


if __name__ == "__main__":
    main()
