"""
Paso 2 · Transacción ACID multi-documento: compra de un juego.

Una compra modifica TRES documentos en TRES colecciones:
  1. juegos    -> stock - 1
  2. ordenes   -> se crea la orden
  3. usuarios  -> saldo - precio

O se aplican los tres cambios, o ninguno. El script corre dos escenarios:

  ÉXITO: Ana (saldo $50.000) compra Hollow Knight ($15.000)
         -> commit_transaction(): los tres cambios quedan confirmados.

  FALLO: Bruno (saldo $5.000) compra Hollow Knight ($15.000)
         -> el stock ya se descontó y la orden ya se insertó cuando el
            tercer paso detecta saldo insuficiente.
         -> abort_transaction(): el motor revierte TODO y la base queda
            exactamente como estaba.

Uso:
  python scripts/03_transaccion_compra.py          # ambos escenarios
  python scripts/03_transaccion_compra.py exito
  python scripts/03_transaccion_compra.py fallo

Tip: corré antes 01_seed.py para partir de datos conocidos.
"""

import sys
from datetime import datetime, timezone

from pymongo import ReturnDocument
from pymongo.errors import PyMongoError
from pymongo.read_concern import ReadConcern
from pymongo.write_concern import WriteConcern

from config import DB_NAME, get_client

MAX_REINTENTOS = 3


class ReglaDeNegocioError(Exception):
    """Una regla del dominio se violó a mitad de la compra."""


# ─────────────────────────────────────────────────────────────────────────────
#  Núcleo de la transacción
# ─────────────────────────────────────────────────────────────────────────────

def comprar_juego(client, email, titulo):
    """
    Ejecuta la compra completa. Reintenta solo los errores que MongoDB marca
    como transitorios (por ejemplo, un cambio de primario en plena
    transacción). Los errores de negocio NO se reintentan.
    """
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            return _compra_en_transaccion(client, email, titulo)
        except PyMongoError as e:
            if e.has_error_label("TransientTransactionError") and intento < MAX_REINTENTOS:
                print(f"  ↻ Error transitorio ({e}); reintentando transacción completa...")
                continue
            raise


def _compra_en_transaccion(client, email, titulo):
    db = client[DB_NAME]

    # Una sesión agrupa todas las operaciones de la transacción.
    with client.start_session() as session:
        # readConcern "snapshot": todas las lecturas ven la misma foto de la base.
        # writeConcern "majority": el commit espera a que la mayoría de los nodos
        #   con datos lo tenga, así sobrevive a una caída del primario.
        session.start_transaction(
            read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern("majority", wtimeout=5000),
        )
        try:
            # Paso 1: descontar stock (solo si hay unidades disponibles).
            juego = db.juegos.find_one_and_update(
                {"titulo": titulo, "stock": {"$gt": 0}},
                {"$inc": {"stock": -1}},
                return_document=ReturnDocument.AFTER,
                session=session,          # ← sin esto, la operación queda FUERA de la transacción
            )
            if juego is None:
                raise ReglaDeNegocioError(f"'{titulo}' no existe o no tiene stock")
            print(f"  1) Stock descontado dentro de la transacción → {juego['stock']}")

            # Aislamiento (la "I" de ACID): fuera de la sesión, nadie ve el cambio aún.
            visto_afuera = db.juegos.find_one({"_id": juego["_id"]})["stock"]
            print(f"     (una lectura FUERA de la transacción todavía ve stock = {visto_afuera})")

            usuario = db.usuarios.find_one({"email": email}, session=session)
            if usuario is None:
                raise ReglaDeNegocioError(f"El usuario {email} no existe")

            # Paso 2: registrar la orden.
            orden = {
                "usuarioId": usuario["_id"],
                "juegoId": juego["_id"],
                "titulo": juego["titulo"],
                "precio": juego["precio"],
                "fecha": datetime.now(timezone.utc),
            }
            db.ordenes.insert_one(orden, session=session)
            print(f"  2) Orden creada dentro de la transacción → {orden['_id']}")

            # Paso 3: cobrar. El filtro saldo >= precio ES la regla de negocio:
            # si no hay saldo suficiente, no coincide ningún documento.
            res = db.usuarios.update_one(
                {"_id": usuario["_id"], "saldo": {"$gte": juego["precio"]}},
                {"$inc": {"saldo": -juego["precio"]}},
                session=session,
            )
            if res.matched_count == 0:
                raise ReglaDeNegocioError(
                    f"Saldo insuficiente: {usuario['nombre']} tiene ${usuario['saldo']:,} "
                    f"y el juego cuesta ${juego['precio']:,}"
                )
            print(f"  3) Saldo descontado: ${juego['precio']:,}")

            _commit_con_reintento(session)
            print("  ✅ commit_transaction(): los 3 cambios quedaron confirmados")
            return orden

        except Exception as e:
            # Cualquier error (de negocio o técnico) deshace TODO lo hecho en la sesión.
            if session.in_transaction:
                session.abort_transaction()
                print(f"  ⛔ abort_transaction() → {e}")
            raise


def _commit_con_reintento(session):
    """
    Si la red falla justo durante el commit, el resultado es desconocido
    (etiqueta UnknownTransactionCommitResult). Reintentar el commit es seguro:
    MongoDB lo hace idempotente.
    """
    for intento in range(1, MAX_REINTENTOS + 1):
        try:
            session.commit_transaction()
            return
        except PyMongoError as e:
            if e.has_error_label("UnknownTransactionCommitResult") and intento < MAX_REINTENTOS:
                print("  ↻ Resultado del commit desconocido; reintentando commit...")
                continue
            raise


# ─────────────────────────────────────────────────────────────────────────────
#  Escenarios de demostración
# ─────────────────────────────────────────────────────────────────────────────

def foto(db, email, titulo):
    """Estado relevante de la base, para comparar antes y después."""
    return {
        "saldo": db.usuarios.find_one({"email": email})["saldo"],
        "stock": db.juegos.find_one({"titulo": titulo})["stock"],
        "ordenes": db.ordenes.count_documents({}),
    }


def mostrar(etiqueta, f):
    print(f"  {etiqueta:<8} saldo=${f['saldo']:>7,}  stock={f['stock']:>2}  ordenes={f['ordenes']}")


def escenario(client, nombre, email, titulo, debe_fallar):
    db = client[DB_NAME]
    print(f"\n═══ ESCENARIO {nombre}: {email} compra '{titulo}' ═══")
    antes = foto(db, email, titulo)
    mostrar("ANTES", antes)

    try:
        comprar_juego(client, email, titulo)
    except ReglaDeNegocioError:
        pass  # esperado en el escenario de fallo; ya se informó en el abort

    despues = foto(db, email, titulo)
    mostrar("DESPUÉS", despues)

    if debe_fallar:
        assert antes == despues, "¡La base cambió pese al rollback!"
        print("  ✔ Rollback verificado: la base quedó intacta.")
    else:
        assert despues["stock"] == antes["stock"] - 1
        assert despues["ordenes"] == antes["ordenes"] + 1
        assert despues["saldo"] < antes["saldo"]
        print("  ✔ Commit verificado: stock, orden y saldo cambiaron juntos.")


def main():
    client = get_client()
    modo = sys.argv[1] if len(sys.argv) > 1 else "ambos"

    if modo in ("exito", "ambos"):
        escenario(client, "DE ÉXITO", "ana@mail.com", "Hollow Knight", debe_fallar=False)
    if modo in ("fallo", "ambos"):
        escenario(client, "DE FALLO", "bruno@mail.com", "Hollow Knight", debe_fallar=True)


if __name__ == "__main__":
    main()
