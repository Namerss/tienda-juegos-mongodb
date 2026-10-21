"""
Paso 3 · Genera el keyFile que comparten los tres nodos.

Con la autorización activada, los miembros del Replica Set también tienen que
probar su identidad entre sí. El keyFile es esa "contraseña interna": sin él,
un mongod cualquiera no podría unirse al clúster ni replicar los datos.

El archivo queda en secrets/ (ignorado por git: NUNCA se sube al repo).
Uso:  python scripts/generar_keyfile.py
"""

import base64
import os
import secrets

RUTA = os.path.join(os.path.dirname(__file__), "..", "secrets", "mongo-keyfile")


def main():
    os.makedirs(os.path.dirname(RUTA), exist_ok=True)
    if os.path.exists(RUTA):
        print(f"Ya existe {os.path.normpath(RUTA)}; no se sobrescribe.")
        return
    clave = base64.b64encode(secrets.token_bytes(756)).decode()  # 1008 caracteres base64
    with open(RUTA, "w", newline="\n") as f:
        f.write(clave + "\n")
    if os.name == "posix":
        os.chmod(RUTA, 0o400)  # mongod exige que solo el dueño pueda leerlo
    print(f"keyFile generado en {os.path.normpath(RUTA)}")


if __name__ == "__main__":
    main()
