"""
Capa de datos del panel de administración: catálogo de productos, importación masiva
e historial de pedidos. Funciones SÍNCRONAS; los endpoints las llaman en un hilo.

Reglas que protegen el historial:
  * Los productos NUNCA se borran: se ocultan con `disponible = FALSE`.
  * Cada línea de pedido guarda el nombre y el precio del momento de la venta
    (Detalle_Pedidos.nombre_producto / precio_unitario): cambiar un precio hoy no
    altera lo vendido ayer.
  * Toda modificación de precio queda en Historial_Precios.
"""
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any, Dict, List, Optional

from fastapi import HTTPException
from mysql.connector import errors as mysql_errors

from catalogo import normalizar_nombre
from db import db
from modelos import ConfirmarImportacion, ProductoEditar, ProductoNuevo

COLUMNAS_PRODUCTO = "id_producto, nombre, precio, categoria, tipo_preparacion, disponible"


def _producto_json(r: Dict[str, Any]) -> Dict[str, Any]:
    r = dict(r)
    r["disponible"] = bool(r["disponible"])
    return r


def _like(texto: str) -> str:
    """Escapa % _ \\ para que el texto del usuario se busque literalmente."""
    for c in ("\\", "%", "_"):
        texto = texto.replace(c, "\\" + c)
    return f"%{texto}%"


# ---------------------------------------------------------------------------
# CATÁLOGO
# ---------------------------------------------------------------------------
def listar_productos(
    q: Optional[str] = None, categoria: Optional[str] = None, disponible: Optional[bool] = None
) -> List[dict]:
    sql = f"SELECT {COLUMNAS_PRODUCTO} FROM Productos WHERE 1=1"
    params: list = []
    if q and q.strip():
        sql += " AND nombre_norm LIKE %s"
        params.append(_like(normalizar_nombre(q)))
    if categoria:
        sql += " AND categoria = %s"
        params.append(categoria)
    if disponible is not None:
        sql += " AND disponible = %s"
        params.append(1 if disponible else 0)
    sql += " ORDER BY categoria, nombre"
    with db() as (_, cur):
        cur.execute(sql, tuple(params))
        return [_producto_json(r) for r in cur.fetchall()]


def crear_producto(p: ProductoNuevo) -> dict:
    clave = normalizar_nombre(p.nombre)
    try:
        with db(transaccion=True) as (_, cur):
            cur.execute("SELECT id_producto, nombre FROM Productos WHERE nombre_norm = %s", (clave,))
            existente = cur.fetchone()
            if existente:
                raise HTTPException(
                    409, f"Ya existe el producto «{existente['nombre']}» (id {existente['id_producto']})"
                )
            cur.execute(
                "INSERT INTO Productos (nombre, nombre_norm, precio, categoria, tipo_preparacion, disponible) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (p.nombre, clave, p.precio, p.categoria, p.tipo_preparacion, 1 if p.disponible else 0),
            )
            id_producto = cur.lastrowid
            cur.execute(
                "INSERT INTO Historial_Precios (id_producto, precio_anterior, precio_nuevo, origen) "
                "VALUES (%s, NULL, %s, 'creacion')",
                (id_producto, p.precio),
            )
    except mysql_errors.IntegrityError:
        raise HTTPException(409, "Ya existe un producto con ese nombre")
    return obtener_producto(id_producto)


def obtener_producto(id_producto: int) -> dict:
    with db() as (_, cur):
        cur.execute(f"SELECT {COLUMNAS_PRODUCTO} FROM Productos WHERE id_producto = %s", (id_producto,))
        fila = cur.fetchone()
    if not fila:
        raise HTTPException(404, "Producto no encontrado")
    return _producto_json(fila)


def editar_producto(id_producto: int, cambios: ProductoEditar) -> dict:
    datos = cambios.model_dump(exclude_unset=True)
    try:
        with db(transaccion=True) as (_, cur):
            cur.execute(
                "SELECT id_producto, nombre, nombre_norm, precio FROM Productos "
                "WHERE id_producto = %s FOR UPDATE",
                (id_producto,),
            )
            actual = cur.fetchone()
            if not actual:
                raise HTTPException(404, "Producto no encontrado")

            sets: List[str] = []
            params: list = []

            if "nombre" in datos and datos["nombre"] is not None:
                clave = normalizar_nombre(datos["nombre"])
                cur.execute(
                    "SELECT id_producto, nombre FROM Productos WHERE nombre_norm = %s AND id_producto <> %s",
                    (clave, id_producto),
                )
                otro = cur.fetchone()
                if otro:
                    raise HTTPException(409, f"Ya existe otro producto llamado «{otro['nombre']}»")
                sets += ["nombre = %s", "nombre_norm = %s"]
                params += [datos["nombre"], clave]

            precio_cambia = False
            if "precio" in datos and datos["precio"] is not None:
                nuevo = Decimal(datos["precio"]).quantize(Decimal("0.01"))
                if nuevo != Decimal(actual["precio"]).quantize(Decimal("0.01")):
                    precio_cambia = True
                    sets.append("precio = %s")
                    params.append(nuevo)

            for campo in ("categoria", "tipo_preparacion"):
                if datos.get(campo) is not None:
                    sets.append(f"{campo} = %s")
                    params.append(datos[campo])
            if datos.get("disponible") is not None:
                sets.append("disponible = %s")
                params.append(1 if datos["disponible"] else 0)

            if sets:
                cur.execute(
                    f"UPDATE Productos SET {', '.join(sets)} WHERE id_producto = %s",
                    tuple(params + [id_producto]),
                )
            if precio_cambia:
                cur.execute(
                    "INSERT INTO Historial_Precios (id_producto, precio_anterior, precio_nuevo, origen) "
                    "VALUES (%s, %s, %s, 'manual')",
                    (id_producto, actual["precio"], nuevo),
                )
    except mysql_errors.IntegrityError:
        raise HTTPException(409, "Ya existe un producto con ese nombre")
    return obtener_producto(id_producto)


def historial_precios_producto(id_producto: int, limite: int = 50) -> List[dict]:
    with db() as (_, cur):
        cur.execute(
            "SELECT precio_anterior, precio_nuevo, origen, cambiado_en FROM Historial_Precios "
            "WHERE id_producto = %s ORDER BY id_historial DESC LIMIT %s",
            (id_producto, limite),
        )
        return cur.fetchall()


# ---------------------------------------------------------------------------
# IMPORTACIÓN MASIVA
# ---------------------------------------------------------------------------
def catalogo_para_importar() -> List[dict]:
    with db() as (_, cur):
        cur.execute("SELECT id_producto, nombre, nombre_norm, precio, disponible FROM Productos")
        filas = cur.fetchall()
    for f in filas:
        f["nombre_norm"] = f["nombre_norm"] or normalizar_nombre(f["nombre"])
        f["disponible"] = bool(f["disponible"])
    return filas


def aplicar_importacion(req: ConfirmarImportacion) -> dict:
    # Se vuelve a validar TODO en el servidor: nunca se confía en lo que manda el navegador
    claves_payload: Dict[str, str] = {}
    for f in req.filas:
        clave = normalizar_nombre(f.nombre)
        if clave in claves_payload:
            raise HTTPException(400, f"«{f.nombre}» viene repetido en la importación")
        claves_payload[clave] = f.nombre

    resultado = {"creados": 0, "actualizados": 0, "sin_cambios": 0, "desactivados": 0}
    try:
        with db(transaccion=True) as (_, cur):
            cur.execute("SELECT id_producto, nombre, nombre_norm, precio, disponible FROM Productos")
            existentes = {
                (r["nombre_norm"] or normalizar_nombre(r["nombre"])): r for r in cur.fetchall()
            }

            for f in req.filas:
                clave = normalizar_nombre(f.nombre)
                precio = Decimal(f.precio).quantize(Decimal("0.01"))
                ya = existentes.get(clave)
                if ya is None:
                    cur.execute(
                        "INSERT INTO Productos (nombre, nombre_norm, precio, categoria, tipo_preparacion, disponible) "
                        "VALUES (%s, %s, %s, %s, %s, 1)",
                        (f.nombre, clave, precio, f.categoria, f.tipo_preparacion),
                    )
                    cur.execute(
                        "INSERT INTO Historial_Precios (id_producto, precio_anterior, precio_nuevo, origen) "
                        "VALUES (%s, NULL, %s, 'excel')",
                        (cur.lastrowid, precio),
                    )
                    resultado["creados"] += 1
                elif req.actualizar_precios and Decimal(ya["precio"]).quantize(Decimal("0.01")) != precio:
                    cur.execute(
                        "UPDATE Productos SET precio = %s WHERE id_producto = %s",
                        (precio, ya["id_producto"]),
                    )
                    cur.execute(
                        "INSERT INTO Historial_Precios (id_producto, precio_anterior, precio_nuevo, origen) "
                        "VALUES (%s, %s, %s, 'excel')",
                        (ya["id_producto"], ya["precio"], precio),
                    )
                    resultado["actualizados"] += 1
                else:
                    resultado["sin_cambios"] += 1

            if req.desactivar_faltantes:
                en_archivo = {normalizar_nombre(c) for c in req.claves_archivo} | set(claves_payload)
                ids = [
                    r["id_producto"]
                    for k, r in existentes.items()
                    if r["disponible"] and k not in en_archivo
                ]
                for i in range(0, len(ids), 500):
                    lote = ids[i : i + 500]
                    cur.execute(
                        f"UPDATE Productos SET disponible = 0 WHERE id_producto IN ({','.join(['%s'] * len(lote))})",
                        tuple(lote),
                    )
                resultado["desactivados"] = len(ids)
    except mysql_errors.IntegrityError:
        # Dos importaciones simultáneas: el índice UNIQUE evitó el duplicado; se revierte todo
        raise HTTPException(409, "Otro cambio simultáneo creó un producto igual. Intenta de nuevo.")
    return resultado


# ---------------------------------------------------------------------------
# HISTORIAL DE PEDIDOS
# ---------------------------------------------------------------------------
@dataclass
class FiltrosHistorial:
    desde: Optional[date] = None
    hasta: Optional[date] = None
    estado: Optional[str] = None
    matricula: Optional[str] = None
    producto: Optional[str] = None
    metodo_pago: Optional[str] = None
    id_pedido: Optional[int] = None


def _where(f: FiltrosHistorial):
    cond: List[str] = []
    params: list = []
    if f.desde:
        cond.append("p.fecha_hora >= %s")
        params.append(datetime.combine(f.desde, time.min))
    if f.hasta:  # inclusivo: hasta el final de ese día
        cond.append("p.fecha_hora < %s")
        params.append(datetime.combine(f.hasta + timedelta(days=1), time.min))
    if f.estado:
        cond.append("p.estado = %s")
        params.append(f.estado)
    if f.matricula and f.matricula.strip():
        cond.append("p.matricula LIKE %s")
        params.append(_like(f.matricula.strip()))
    if f.metodo_pago:
        cond.append("p.metodo_pago = %s")
        params.append(f.metodo_pago)
    if f.id_pedido:
        cond.append("p.id_pedido = %s")
        params.append(f.id_pedido)
    if f.producto and f.producto.strip():
        cond.append(
            "EXISTS (SELECT 1 FROM Detalle_Pedidos d WHERE d.id_pedido = p.id_pedido "
            "AND d.nombre_producto LIKE %s)"
        )
        params.append(_like(f.producto.strip()))
    return (" WHERE " + " AND ".join(cond)) if cond else "", params


def _items(cur, ids: List[int]) -> Dict[int, list]:
    if not ids:
        return {}
    cur.execute(
        f"""
        SELECT d.id_pedido, d.cantidad, d.notas,
               COALESCE(d.nombre_producto, pr.nombre) AS nombre,
               COALESCE(d.precio_unitario, pr.precio) AS precio_unitario
        FROM Detalle_Pedidos d
        LEFT JOIN Productos pr ON pr.id_producto = d.id_producto
        WHERE d.id_pedido IN ({','.join(['%s'] * len(ids))})
        ORDER BY d.id_detalle
        """,
        tuple(ids),
    )
    por_pedido: Dict[int, list] = {i: [] for i in ids}
    for r in cur.fetchall():
        por_pedido[r["id_pedido"]].append(
            {
                "cantidad": r["cantidad"],
                "nombre": r["nombre"],
                "precio_unitario": r["precio_unitario"],
                "notas": r["notas"],
            }
        )
    return por_pedido


def listar_historial(f: FiltrosHistorial, limite: int = 50, offset: int = 0) -> dict:
    where, params = _where(f)
    with db() as (_, cur):
        cur.execute(
            f"SELECT COUNT(*) AS n, COALESCE(SUM(p.total), 0) AS ventas FROM Pedidos p{where}",
            tuple(params),
        )
        resumen = cur.fetchone()
        cur.execute(
            f"""
            SELECT p.id_pedido, p.nombre_estudiante, p.matricula, p.estado,
                   p.fecha_hora, p.total, p.metodo_pago
            FROM Pedidos p{where}
            ORDER BY p.fecha_hora DESC, p.id_pedido DESC
            LIMIT %s OFFSET %s
            """,
            tuple(params + [limite, offset]),
        )
        pedidos = cur.fetchall()
        items = _items(cur, [p["id_pedido"] for p in pedidos])
        for p in pedidos:
            p["items"] = items[p["id_pedido"]]
    n = resumen["n"]
    ventas = Decimal(resumen["ventas"])
    return {
        "total_pedidos": n,
        "ventas": ventas,
        "ticket_promedio": (ventas / n).quantize(Decimal("0.01")) if n else Decimal("0.00"),
        "pedidos": pedidos,
        "limite": limite,
        "offset": offset,
    }


def ranking_productos(f: FiltrosHistorial, limite: int = 15) -> List[dict]:
    where, params = _where(f)
    with db() as (_, cur):
        cur.execute(
            f"""
            SELECT COALESCE(MAX(d.nombre_producto), MAX(pr.nombre)) AS nombre,
                   SUM(d.cantidad) AS unidades,
                   SUM(d.cantidad * COALESCE(d.precio_unitario, pr.precio)) AS importe
            FROM Detalle_Pedidos d
            JOIN Pedidos p ON p.id_pedido = d.id_pedido
            LEFT JOIN Productos pr ON pr.id_producto = d.id_producto
            {where}
            GROUP BY d.id_producto
            ORDER BY unidades DESC, importe DESC
            LIMIT %s
            """,
            tuple(params + [limite]),
        )
        return cur.fetchall()


def pedidos_para_exportar(f: FiltrosHistorial, maximo: int = 20000) -> List[dict]:
    return listar_historial(f, limite=maximo, offset=0)["pedidos"]
