"""Conexión a MySQL/MariaDB con pool. La configuración puede venir de variables de
entorno (útil para tener una BD de pruebas separada):

    DB_HOST (localhost)  DB_PORT (3306)  DB_USER (root)  DB_PASSWORD ("")
    DB_NAME (cafeteria_umg)
"""
import os
from contextlib import contextmanager
from typing import Optional

from mysql.connector import pooling


def _config() -> dict:
    return {
        "host": os.environ.get("DB_HOST", "localhost"),
        "port": int(os.environ.get("DB_PORT", "3306")),
        "user": os.environ.get("DB_USER", "root"),
        "password": os.environ.get("DB_PASSWORD", ""),
        "database": os.environ.get("DB_NAME", "cafeteria_umg"),
        "charset": "utf8mb4",
        "autocommit": True,  # las escrituras usan transacción explícita (ver db())
    }


_pool: Optional[pooling.MySQLConnectionPool] = None


def get_pool() -> pooling.MySQLConnectionPool:
    global _pool
    if _pool is None:  # se crea al primer uso: el servidor arranca aunque MySQL tarde
        _pool = pooling.MySQLConnectionPool(pool_name="cafeteria", pool_size=10, **_config())
    return _pool


def reset_pool() -> None:
    """Solo para pruebas: descarta el pool para releer la configuración."""
    global _pool
    _pool = None


@contextmanager
def db(transaccion: bool = False):
    """Entrega (conn, cursor). Siempre devuelve la conexión al pool."""
    conn = get_pool().get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        if transaccion:
            conn.start_transaction()
        yield conn, cursor
        if transaccion:
            conn.commit()
    except Exception:
        if transaccion:
            conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
