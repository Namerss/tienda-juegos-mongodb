"""
Crea (o reinicia) la base "tiendaJuegos" con datos de prueba.

Colecciones:
  usuarios  { nombre, email (único), saldo >= 0 }
  juegos    { titulo, plataforma, precio >= 0, stock >= 0 }
  ordenes   { usuarioId, juegoId, titulo, precio, fecha }

Los validadores $jsonSchema son una segunda línea de defensa: aunque el
código tuviera un error, el motor rechaza un saldo o stock negativo.

Volvé a correr este script cuando quieras dejar los datos como al principio.
Uso:  python scripts/01_seed.py
"""

from pymongo import ASCENDING

from config import DB_NAME, get_db

VALIDADORES = {
    "usuarios": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["nombre", "email", "saldo"],
            "properties": {
                "nombre": {"bsonType": "string"},
                "email": {"bsonType": "string"},
                "saldo": {"bsonType": "number", "minimum": 0},
            },
        }
    },
    "juegos": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["titulo", "plataforma", "precio", "stock"],
            "properties": {
                "titulo": {"bsonType": "string"},
                "plataforma": {"bsonType": "string"},
                "precio": {"bsonType": "number", "minimum": 0},
                "stock": {"bsonType": "int", "minimum": 0},
            },
        }
    },
    "ordenes": {
        "$jsonSchema": {
            "bsonType": "object",
            "required": ["usuarioId", "juegoId", "precio", "fecha"],
        }
    },
}

USUARIOS = [
    {"nombre": "Ana", "email": "ana@mail.com", "saldo": 50000},
    {"nombre": "Bruno", "email": "bruno@mail.com", "saldo": 5000},  # saldo bajo a propósito
    {"nombre": "Carla", "email": "carla@mail.com", "saldo": 120000},
]

JUEGOS = [
    {"titulo": "Hollow Knight", "plataforma": "PC", "precio": 15000, "stock": 10},
    {"titulo": "Celeste", "plataforma": "PC", "precio": 12000, "stock": 5},
    {"titulo": "Stardew Valley", "plataforma": "Switch", "precio": 18000, "stock": 8},
    {"titulo": "Hades", "plataforma": "PS5", "precio": 25000, "stock": 3},
    {"titulo": "Cuphead", "plataforma": "PC", "precio": 14000, "stock": 0},  # sin stock
]


def main():
    db = get_db()

    for nombre, validador in VALIDADORES.items():
        db.drop_collection(nombre)
        db.create_collection(nombre, validator=validador)

    db.usuarios.create_index([("email", ASCENDING)], unique=True)
    db.juegos.create_index([("titulo", ASCENDING), ("plataforma", ASCENDING)], unique=True)
    db.ordenes.create_index([("usuarioId", ASCENDING), ("fecha", ASCENDING)])

    db.usuarios.insert_many(USUARIOS)
    db.juegos.insert_many(JUEGOS)

    print(f"Base '{DB_NAME}' lista:")
    for col in ("usuarios", "juegos", "ordenes"):
        print(f"  {col:<9} {db[col].count_documents({})} documentos")


if __name__ == "__main__":
    main()
