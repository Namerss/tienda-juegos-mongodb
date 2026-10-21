"""
Paso 3 · Crea los usuarios del sistema (principio de privilegios mínimos).

  admin        -> rol "root" sobre todo el clúster. Uso exclusivo de
                  administración (alta de usuarios, mantenimiento). La
                  aplicación NUNCA se conecta con él.
  tienda_app   -> rol "readWrite" SOLO sobre la base tiendaJuegos. Es el
                  usuario de la aplicación: puede leer y escribir sus datos,
                  pero no ver otras bases, crear usuarios ni administrar el
                  clúster.

Se corre UNA vez, con los nodos todavía en modo config/inicial (sin auth).
Después se reinician con config/seguro (ver README, Paso 3).

Las contraseñas se piden por teclado (o se toman de ADMIN_PASS / APP_PASS en
.env); nunca se escriben en el código.

Uso:  python scripts/04_crear_usuarios.py
"""

import os
from getpass import getpass

from pymongo.errors import OperationFailure

from config import DB_NAME, get_client

ADMIN_USER = os.getenv("ADMIN_USER", "admin")
APP_USER = os.getenv("APP_USER", "tienda_app")


def pedir(var, prompt):
    valor = os.getenv(var) or getpass(prompt)
    if len(valor) < 12:
        raise SystemExit("Usá una contraseña de al menos 12 caracteres.")
    return valor


def crear_o_actualizar(admin_db, usuario, password, roles):
    try:
        admin_db.command("createUser", usuario, pwd=password, roles=roles)
        print(f"  ✔ creado      {usuario:<12} roles={roles}")
    except OperationFailure as e:
        if e.code != 51003 and "already exists" not in str(e):  # 51003 = el usuario ya existe
            raise
        admin_db.command("updateUser", usuario, pwd=password, roles=roles)
        print(f"  ↻ actualizado {usuario:<12} roles={roles}")


def main():
    admin_pass = pedir("ADMIN_PASS", f"Contraseña para '{ADMIN_USER}': ")
    app_pass = pedir("APP_PASS", f"Contraseña para '{APP_USER}': ")

    client = get_client()  # todavía sin autenticación
    admin_db = client.admin  # los usuarios se guardan en la base "admin"

    crear_o_actualizar(admin_db, ADMIN_USER, admin_pass, [{"role": "root", "db": "admin"}])
    crear_o_actualizar(admin_db, APP_USER, app_pass, [{"role": "readWrite", "db": DB_NAME}])

    print("\nListo. Ahora reiniciá los nodos con config/seguro (security.authorization: enabled).")


if __name__ == "__main__":
    main()
