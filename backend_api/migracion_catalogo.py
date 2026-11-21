"""
Migración de la base de datos para el catálogo editable, la importación desde Excel y el
historial. Es IDEMPOTENTE: puedes correrla varias veces, solo aplica lo que falte.

    cd backend_api
    python migracion_catalogo.py

Antes (recomendado), respalda:  mysqldump -u root cafeteria_umg > respaldo.sql

Qué agrega
  Productos          nombre_norm (único: evita duplicados 'Café'/'cafe '), creado_en, actualizado_en
  Detalle_Pedidos    nombre_producto y precio_unitario  (foto del producto al momento de la venta)
  Historial_Precios  tabla nueva: bitácora de cambios de precio
  Pedidos            índices por fecha y matrícula (consultas del historial)
"""
import sys

from catalogo import normalizar_nombre
from db import db


def existe_columna(cur, tabla: str, columna: str) -> bool:
    # LOWER(): en Windows (XAMPP) MySQL guarda los nombres de tabla en minúsculas
    cur.execute(
        "SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
        "AND LOWER(TABLE_NAME) = LOWER(%s) AND COLUMN_NAME = %s",
        (tabla, columna),
    )
    return cur.fetchone()["n"] > 0


def existe_indice(cur, tabla: str, indice: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) AS n FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() "
        "AND LOWER(TABLE_NAME) = LOWER(%s) AND INDEX_NAME = %s",
        (tabla, indice),
    )
    return cur.fetchone()["n"] > 0


def existe_tabla(cur, tabla: str) -> bool:
    cur.execute(
        "SELECT COUNT(*) AS n FROM information_schema.TABLES WHERE TABLE_SCHEMA = DATABASE() "
        "AND LOWER(TABLE_NAME) = LOWER(%s)",
        (tabla,),
    )
    return cur.fetchone()["n"] > 0


def migrar() -> int:
    avisos = 0
    with db() as (_, cur):
        for t in ("Productos", "Pedidos", "Detalle_Pedidos"):
            if not existe_tabla(cur, t):
                print(f"✖ No existe la tabla {t}. Ejecuta primero bd.sql.")
                return 1

        # 1) Productos ------------------------------------------------------
        if not existe_columna(cur, "Productos", "nombre_norm"):
            cur.execute("ALTER TABLE Productos ADD COLUMN nombre_norm VARCHAR(120) NULL AFTER nombre")
            print("✔ Productos.nombre_norm agregada")
        if not existe_columna(cur, "Productos", "creado_en"):
            cur.execute(
                "ALTER TABLE Productos ADD COLUMN creado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP"
            )
            print("✔ Productos.creado_en agregada")
        if not existe_columna(cur, "Productos", "actualizado_en"):
            cur.execute(
                "ALTER TABLE Productos ADD COLUMN actualizado_en TIMESTAMP NOT NULL "
                "DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP"
            )
            print("✔ Productos.actualizado_en agregada")

        # Calcula/refresca nombre_norm con la MISMA función que usa la API. Se revisan todos
        # (no solo los vacíos): así, si renombraste un producto a mano en MySQL, su clave se corrige.
        cur.execute("SELECT id_producto, nombre, nombre_norm FROM Productos")
        pendientes = [
            p for p in cur.fetchall() if p["nombre_norm"] != normalizar_nombre(p["nombre"])
        ]
        for p in pendientes:
            cur.execute(
                "UPDATE Productos SET nombre_norm = %s WHERE id_producto = %s",
                (normalizar_nombre(p["nombre"]), p["id_producto"]),
            )
        if pendientes:
            print(f"✔ nombre_norm calculado para {len(pendientes)} producto(s)")

        # Índice único: solo si no hay duplicados ya existentes
        if not existe_indice(cur, "Productos", "uq_productos_nombre_norm"):
            cur.execute(
                "SELECT nombre_norm, COUNT(*) AS n, GROUP_CONCAT(CONCAT(id_producto, ':', nombre) "
                "SEPARATOR ' | ') AS detalle FROM Productos GROUP BY nombre_norm HAVING COUNT(*) > 1"
            )
            duplicados = cur.fetchall()
            if duplicados:
                avisos += 1
                print("⚠ Hay productos duplicados; NO se creó el índice único todavía:")
                for d in duplicados:
                    print(f"    {d['detalle']}")
                print(
                    "  Resuélvelos RENOMBRANDO uno (ocultarlo no basta: el índice único mira el nombre):\n"
                    "      UPDATE Productos SET nombre = 'Nombre distinto' WHERE id_producto = <id>;\n"
                    "  y vuelve a correr este script (recalcula las claves solo).\n"
                    "  No los borres si ya tienen pedidos: Detalle_Pedidos los referencia."
                )
            else:
                cur.execute("ALTER TABLE Productos MODIFY nombre_norm VARCHAR(120) NOT NULL")
                cur.execute(
                    "ALTER TABLE Productos ADD UNIQUE KEY uq_productos_nombre_norm (nombre_norm)"
                )
                print("✔ Índice único por nombre creado (ya no se pueden duplicar productos)")

        # 2) Detalle_Pedidos: foto del producto al vender -------------------
        agregado = False
        if not existe_columna(cur, "Detalle_Pedidos", "nombre_producto"):
            cur.execute("ALTER TABLE Detalle_Pedidos ADD COLUMN nombre_producto VARCHAR(100) NULL")
            agregado = True
        if not existe_columna(cur, "Detalle_Pedidos", "precio_unitario"):
            cur.execute("ALTER TABLE Detalle_Pedidos ADD COLUMN precio_unitario DECIMAL(10,2) NULL")
            agregado = True
        cur.execute(
            "UPDATE Detalle_Pedidos d JOIN Productos p ON p.id_producto = d.id_producto "
            "SET d.nombre_producto = p.nombre, d.precio_unitario = p.precio "
            "WHERE d.precio_unitario IS NULL OR d.nombre_producto IS NULL"
        )
        if agregado or cur.rowcount:
            print(
                f"✔ Detalle_Pedidos: nombre/precio de venta guardados ({cur.rowcount} línea(s) antiguas "
                "rellenadas con el precio ACTUAL: es lo único disponible de pedidos pasados)"
            )

        # 3) Historial_Precios ---------------------------------------------
        if not existe_tabla(cur, "Historial_Precios"):
            cur.execute(
                """
                CREATE TABLE Historial_Precios (
                    id_historial INT AUTO_INCREMENT PRIMARY KEY,
                    id_producto INT NOT NULL,
                    precio_anterior DECIMAL(10,2) NULL,
                    precio_nuevo DECIMAL(10,2) NOT NULL,
                    origen ENUM('manual', 'excel', 'creacion') NOT NULL DEFAULT 'manual',
                    cambiado_en TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_historial_producto (id_producto),
                    FOREIGN KEY (id_producto) REFERENCES Productos(id_producto)
                )
                """
            )
            print("✔ Tabla Historial_Precios creada")
        cur.execute(
            "INSERT INTO Historial_Precios (id_producto, precio_anterior, precio_nuevo, origen) "
            "SELECT p.id_producto, NULL, p.precio, 'creacion' FROM Productos p "
            "WHERE NOT EXISTS (SELECT 1 FROM Historial_Precios h WHERE h.id_producto = p.id_producto)"
        )
        if cur.rowcount:
            print(f"✔ Precio inicial registrado para {cur.rowcount} producto(s)")

        # 4) Índices para el historial de pedidos ---------------------------
        if not existe_indice(cur, "Pedidos", "idx_pedidos_fecha"):
            cur.execute("ALTER TABLE Pedidos ADD INDEX idx_pedidos_fecha (fecha_hora)")
            print("✔ Índice Pedidos.fecha_hora")
        if existe_columna(cur, "Pedidos", "matricula") and not existe_indice(
            cur, "Pedidos", "idx_pedidos_matricula"
        ):
            cur.execute("ALTER TABLE Pedidos ADD INDEX idx_pedidos_matricula (matricula)")
            print("✔ Índice Pedidos.matricula")

    print("\nMigración completa" + (" (con avisos, revisa arriba)." if avisos else "."))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(migrar())
    except Exception as e:
        print(f"✖ Error: {e}")
        sys.exit(1)
