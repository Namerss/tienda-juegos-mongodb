"""
Paso 3 · Auditoría de seguridad automatizada.

Con los nodos corriendo en modo config/seguro, prueba qué puede y qué NO
puede hacer cada tipo de conexión y compara con lo esperado. La tabla final
es la evidencia para el README.

Uso:  python scripts/05_verificar_seguridad.py
"""

import os
from getpass import getpass

from pymongo.errors import OperationFailure

from config import DB_NAME, get_client

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
APP_USER = os.getenv("APP_USER", "tienda_app")


def intentar(accion):
    """Devuelve ('PERMITIDO', detalle) o ('DENEGADO', motivo del servidor)."""
    try:
        r = accion()
        return "PERMITIDO", str(r)[:40]
    except OperationFailure as e:
        return "DENEGADO", f"[{e.code}] {e.details.get('errmsg', e)}"[:60]


def main():
    admin_pass = os.getenv("ADMIN_PASS") or getpass(f"Contraseña de '{ADMIN_USER}': ")
    app_pass = os.getenv("APP_PASS") or getpass(f"Contraseña de '{APP_USER}': ")

    anonimo = get_client(user="")
    app = get_client(user=APP_USER, password=app_pass)
    intruso = get_client(user=APP_USER, password="clave-incorrecta")
    admin = get_client(user=ADMIN_USER, password=admin_pass)

    pruebas = [
        ("Anónimo lee juegos",
         lambda: anonimo[DB_NAME].juegos.find_one(), "DENEGADO"),
        ("Anónimo lista las bases",
         lambda: anonimo.list_database_names(), "DENEGADO"),
        ("Anónimo inserta datos",
         lambda: anonimo[DB_NAME].juegos.insert_one({"titulo": "pwned"}), "DENEGADO"),
        ("Contraseña incorrecta",
         lambda: intruso[DB_NAME].juegos.find_one(), "DENEGADO"),
        ("App lee juegos (su base)",
         lambda: app[DB_NAME].juegos.find_one({}, {"titulo": 1}), "PERMITIDO"),
        ("App escribe en su base",
         lambda: app[DB_NAME].auditoria.insert_one({"prueba": True}).acknowledged, "PERMITIDO"),
        ("App escribe en OTRA base",
         lambda: app["otraBase"].datos.insert_one({"x": 1}), "DENEGADO"),
        # MongoDB no rechaza listDatabases: lo filtra y muestra solo las bases autorizadas.
        ("App lista bases (solo la suya)",
         lambda: app.list_database_names(), "PERMITIDO"),
        ("App crea un usuario",
         lambda: app[DB_NAME].command("createUser", "hacker", pwd="x", roles=[]), "DENEGADO"),
        ("App borra la base completa",
         lambda: app.drop_database(DB_NAME), "DENEGADO"),
        ("Admin lista las bases",
         lambda: admin.list_database_names(), "PERMITIDO"),
    ]

    print(f"\n{'Prueba':<28} {'Esperado':<10} {'Obtenido':<10}    Respuesta del servidor")
    print("─" * 100)
    fallas = 0
    for nombre, accion, esperado in pruebas:
        obtenido, detalle = intentar(accion)
        ok = obtenido == esperado
        fallas += not ok
        print(f"{nombre:<28} {esperado:<10} {obtenido:<10} {'✅' if ok else '❌'}  {detalle}")

    app[DB_NAME].auditoria.drop()  # limpieza de la prueba de escritura
    print("─" * 100)
    print("✔ Todas las pruebas coinciden con lo esperado." if not fallas
          else f"✘ {fallas} prueba(s) no coinciden: revisá la configuración.")


if __name__ == "__main__":
    main()
