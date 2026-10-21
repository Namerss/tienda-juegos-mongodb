"""
Configuración de conexión compartida por todos los scripts.

Los valores se leen de variables de entorno (o de un archivo .env en la raíz
del repo, si está instalado python-dotenv). Así las contraseñas nunca quedan
escritas en el código ni en el repositorio.
"""

import os
from urllib.parse import quote_plus

from pymongo import MongoClient

try:  # .env es opcional
    from dotenv import load_dotenv

    load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))
except ImportError:
    pass

# Miembros con datos del Replica Set. El árbitro no se incluye: no guarda
# datos ni atiende lecturas/escrituras; el driver lo descubre igual.
HOSTS = os.getenv("MONGO_HOSTS", "localhost:27017,localhost:27018")
REPLICA_SET = os.getenv("MONGO_REPLICA_SET", "rs0")
DB_NAME = os.getenv("MONGO_DB", "tiendaJuegos")

# Los tres nodos, para los scripts que hablan con cada uno por separado.
NODOS = {
    "nodo1": "localhost:27017",
    "nodo2": "localhost:27018",
    "arbitro": "localhost:27019",
}


def build_uri(user=None, password=None, auth_db="admin"):
    """Arma la URI del Replica Set. Sin usuario = conexión anónima."""
    user = user if user is not None else os.getenv("MONGO_USER")
    password = password if password is not None else os.getenv("MONGO_PASS")
    params = f"replicaSet={REPLICA_SET}"
    cred = ""
    if user:
        cred = f"{quote_plus(user)}:{quote_plus(password or '')}@"
        params += f"&authSource={auth_db}"
    return f"mongodb://{cred}{HOSTS}/?{params}"


def get_client(user=None, password=None, **kwargs):
    """Cliente conectado al Replica Set (el driver sigue al primario solo)."""
    kwargs.setdefault("serverSelectionTimeoutMS", 5000)
    return MongoClient(build_uri(user, password), **kwargs)


def get_db(**kwargs):
    return get_client(**kwargs)[DB_NAME]
