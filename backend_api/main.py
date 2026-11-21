"""
Cafetería UMG - API

Flujo en tiempo real:
  * La app del alumno abre un WebSocket en  /ws/pedido/{id}  y recibe el estado
    completo del pedido cada vez que la cocina lo cambia.
  * Si el WebSocket falla, la app hace polling a  GET /pedido/{id}  (respaldo).
  * El panel de cocina (admin.html) abre  /ws/cocina  y se refresca al instante
    cuando llega un pedido nuevo o cambia un estado.

Requiere:  pip install fastapi "uvicorn[standard]" mysql-connector-python
(uvicorn[standard] instala 'websockets', sin él los WebSockets NO funcionan)
"""
import asyncio
from contextlib import contextmanager
from pathlib import Path
from typing import Dict, List, Literal, Optional, Set

import mysql.connector
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from mysql.connector import pooling
from pydantic import BaseModel, Field

app = FastAPI(title="Cafetería UMG - API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# ---------------------------------------------------------------------------
# BASE DE DATOS (pool de conexiones: evita agotar MySQL con varios pedidos)
# ---------------------------------------------------------------------------
DB_CONFIG = {
    "host": "localhost",
    "user": "root",
    "password": "",
    "database": "cafeteria_umg",
    "autocommit": True,  # las escrituras usan transacción explícita (ver db())
}

_pool: Optional[pooling.MySQLConnectionPool] = None


def _get_pool() -> pooling.MySQLConnectionPool:
    global _pool
    if _pool is None:  # se crea al primer uso: el servidor arranca aunque MySQL tarde
        _pool = pooling.MySQLConnectionPool(
            pool_name="cafeteria", pool_size=10, **DB_CONFIG
        )
    return _pool


@contextmanager
def db(transaccion: bool = False):
    """Entrega (conn, cursor). Siempre devuelve la conexión al pool."""
    conn = _get_pool().get_connection()
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


# ---------------------------------------------------------------------------
# ESTADOS DEL PEDIDO
# ---------------------------------------------------------------------------
# En la BD:  'En Cola' -> 'Preparando' -> 'Listo' -> 'Entregado'
# En la app: Pendiente -> En preparación -> Listo para recoger -> Entregado
Estado = Literal["En Cola", "Preparando", "Listo", "Entregado"]
ORDEN_ESTADOS: List[str] = ["En Cola", "Preparando", "Listo", "Entregado"]


def transicion_valida(actual: str, nuevo: str) -> bool:
    """Solo se avanza (o se corrige) un paso a la vez; 'Entregado' es final."""
    if actual == nuevo:
        return True
    if actual == "Entregado":
        return False
    return abs(ORDEN_ESTADOS.index(actual) - ORDEN_ESTADOS.index(nuevo)) == 1


# ---------------------------------------------------------------------------
# CAPA DE DATOS (funciones síncronas; los endpoints las llaman en un hilo)
# ---------------------------------------------------------------------------
def _items_de_pedidos(cursor, ids: List[int]) -> Dict[int, list]:
    if not ids:
        return {}
    marcadores = ",".join(["%s"] * len(ids))
    cursor.execute(
        f"""
        SELECT d.id_pedido, d.cantidad, d.notas, p.nombre
        FROM Detalle_Pedidos d
        JOIN Productos p ON d.id_producto = p.id_producto
        WHERE d.id_pedido IN ({marcadores})
        ORDER BY d.id_detalle
        """,
        tuple(ids),
    )
    por_pedido: Dict[int, list] = {i: [] for i in ids}
    for fila in cursor.fetchall():
        por_pedido[fila["id_pedido"]].append(
            {"cantidad": fila["cantidad"], "notas": fila["notas"], "nombre": fila["nombre"]}
        )
    return por_pedido


def snapshot_pedido(id_pedido: int) -> Optional[dict]:
    """Estado completo de UN pedido (lo que ve el alumno)."""
    with db() as (_, cursor):
        cursor.execute(
            """
            SELECT id_pedido, nombre_estudiante, matricula, estado,
                   fecha_hora, total, metodo_pago
            FROM Pedidos WHERE id_pedido = %s
            """,
            (id_pedido,),
        )
        pedido = cursor.fetchone()
        if not pedido:
            return None

        pedido["items"] = _items_de_pedidos(cursor, [id_pedido])[id_pedido]

        # Pedidos que siguen en cocina y entraron antes que éste
        pedido["pedidos_antes"] = 0
        if pedido["estado"] == "En Cola":
            cursor.execute(
                """
                SELECT COUNT(*) AS n FROM Pedidos
                WHERE estado IN ('En Cola', 'Preparando') AND id_pedido < %s
                """,
                (id_pedido,),
            )
            pedido["pedidos_antes"] = cursor.fetchone()["n"]
        return pedido


def pedidos_activos_db() -> List[dict]:
    with db() as (_, cursor):
        cursor.execute(
            """
            SELECT id_pedido, nombre_estudiante, matricula, estado, fecha_hora, total
            FROM Pedidos
            WHERE estado != 'Entregado'
            ORDER BY fecha_hora ASC, id_pedido ASC
            """
        )
        pedidos = cursor.fetchall()
        items = _items_de_pedidos(cursor, [p["id_pedido"] for p in pedidos])
        for p in pedidos:
            p["items"] = items[p["id_pedido"]]
        return pedidos


def crear_pedido_db(pedido: "NuevoPedido") -> dict:
    with db(transaccion=True) as (_, cursor):
        ids = sorted({i.id_producto for i in pedido.items})
        marcadores = ",".join(["%s"] * len(ids))
        cursor.execute(
            f"SELECT id_producto, precio FROM Productos "
            f"WHERE disponible = TRUE AND id_producto IN ({marcadores})",
            tuple(ids),
        )
        precios = {f["id_producto"]: float(f["precio"]) for f in cursor.fetchall()}

        faltantes = [i for i in ids if i not in precios]
        if faltantes:
            raise HTTPException(
                status_code=400,
                detail=f"Producto(s) no encontrado(s) o no disponible(s): {faltantes}",
            )

        total = sum(precios[i.id_producto] * i.cantidad for i in pedido.items)

        cursor.execute(
            "INSERT INTO Pedidos (nombre_estudiante, matricula, total, metodo_pago) "
            "VALUES (%s, %s, %s, %s)",
            (pedido.nombre_estudiante, pedido.matricula, total, pedido.metodo_pago),
        )
        id_pedido = cursor.lastrowid

        for item in pedido.items:
            cursor.execute(
                "INSERT INTO Detalle_Pedidos (id_pedido, id_producto, cantidad, notas) "
                "VALUES (%s, %s, %s, %s)",
                (id_pedido, item.id_producto, item.cantidad, item.notas),
            )
    return {"id_pedido": id_pedido, "total": total}


def cambiar_estado_db(id_pedido: int, nuevo_estado: str) -> dict:
    with db(transaccion=True) as (_, cursor):
        # FOR UPDATE: si dos cocineros pulsan a la vez, el segundo espera
        cursor.execute(
            "SELECT estado FROM Pedidos WHERE id_pedido = %s FOR UPDATE", (id_pedido,)
        )
        fila = cursor.fetchone()
        if not fila:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")

        anterior = fila["estado"]
        if not transicion_valida(anterior, nuevo_estado):
            raise HTTPException(
                status_code=409,
                detail=f"No se puede pasar de '{anterior}' a '{nuevo_estado}'",
            )
        if anterior != nuevo_estado:
            cursor.execute(
                "UPDATE Pedidos SET estado = %s WHERE id_pedido = %s",
                (nuevo_estado, id_pedido),
            )
    return {"anterior": anterior, "nuevo": nuevo_estado, "cambio": anterior != nuevo_estado}


# ---------------------------------------------------------------------------
# WEBSOCKETS
# ---------------------------------------------------------------------------
HEARTBEAT_SEGUNDOS = 20


class GestorWS:
    def __init__(self) -> None:
        self.por_pedido: Dict[int, Set[WebSocket]] = {}
        self.cocina: Set[WebSocket] = set()

    @staticmethod
    async def _enviar(ws: WebSocket, data: dict) -> bool:
        try:
            await ws.send_json(jsonable_encoder(data))  # Decimal/datetime -> JSON
            return True
        except Exception:
            return False

    def agregar_pedido(self, id_pedido: int, ws: WebSocket) -> None:
        self.por_pedido.setdefault(id_pedido, set()).add(ws)

    def quitar_pedido(self, id_pedido: int, ws: WebSocket) -> None:
        sockets = self.por_pedido.get(id_pedido)
        if sockets:
            sockets.discard(ws)
            if not sockets:
                del self.por_pedido[id_pedido]

    async def enviar_a_pedido(self, id_pedido: int, data: dict) -> None:
        for ws in list(self.por_pedido.get(id_pedido, ())):
            if not await self._enviar(ws, data):
                self.quitar_pedido(id_pedido, ws)

    async def avisar_cocina(self, data: dict) -> None:
        for ws in list(self.cocina):
            if not await self._enviar(ws, data):
                self.cocina.discard(ws)


gestor = GestorWS()


async def propagar_cambios() -> None:
    """Reenvía el estado a cada alumno conectado (su 'pedidos_antes' puede haber
    cambiado aunque su pedido no) y le avisa a la cocina que se refresque."""
    for id_pedido in list(gestor.por_pedido.keys()):
        try:
            snap = await run_in_threadpool(snapshot_pedido, id_pedido)
        except Exception:
            continue
        if snap:
            await gestor.enviar_a_pedido(id_pedido, {"tipo": "estado", "pedido": snap})
    await gestor.avisar_cocina({"tipo": "actualizar"})


async def _mantener_abierto(websocket: WebSocket) -> None:
    """Espera mensajes del cliente; si calla, manda 'ping' como latido."""
    while True:
        try:
            await asyncio.wait_for(websocket.receive_text(), timeout=HEARTBEAT_SEGUNDOS)
        except asyncio.TimeoutError:
            await websocket.send_json({"tipo": "ping"})


@app.websocket("/ws/pedido/{id_pedido}")
async def ws_pedido(websocket: WebSocket, id_pedido: int):
    await websocket.accept()
    try:
        snap = await run_in_threadpool(snapshot_pedido, id_pedido)
    except Exception:
        await websocket.close(code=1011)  # error del servidor: el cliente reintenta
        return
    if snap is None:
        await websocket.send_json({"tipo": "error", "detalle": "Pedido no encontrado"})
        await websocket.close(code=4404)  # 4404: el cliente NO debe reintentar
        return

    gestor.agregar_pedido(id_pedido, websocket)
    try:
        await websocket.send_json(jsonable_encoder({"tipo": "estado", "pedido": snap}))
        await _mantener_abierto(websocket)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        gestor.quitar_pedido(id_pedido, websocket)


@app.websocket("/ws/cocina")
async def ws_cocina(websocket: WebSocket):
    await websocket.accept()
    gestor.cocina.add(websocket)
    try:
        await _mantener_abierto(websocket)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        gestor.cocina.discard(websocket)


# ---------------------------------------------------------------------------
# MODELOS
# ---------------------------------------------------------------------------
class ItemPedido(BaseModel):
    id_producto: int
    cantidad: int = Field(default=1, ge=1, le=50)
    notas: str = ""


class NuevoPedido(BaseModel):
    nombre_estudiante: str = Field(min_length=1, max_length=100)
    matricula: str = Field(min_length=1, max_length=20)
    metodo_pago: Literal["Efectivo", "Tarjeta"]
    items: List[ItemPedido] = Field(min_length=1)


class ActualizarEstado(BaseModel):
    nuevo_estado: Estado


# ---------------------------------------------------------------------------
# RUTAS - ALUMNOS
# ---------------------------------------------------------------------------
@app.get("/menu")
def obtener_menu():
    try:
        with db() as (_, cursor):
            cursor.execute("SELECT * FROM Productos WHERE disponible = TRUE")
            return {"menu": cursor.fetchall()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/ordenar")
async def crear_pedido(pedido: NuevoPedido):
    try:
        creado = await run_in_threadpool(crear_pedido_db, pedido)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    await propagar_cambios()  # la cocina ve el pedido al instante
    return {
        "mensaje": "Pedido registrado",
        "numero_orden": creado["id_pedido"],
        "total": creado["total"],
        "estado": "En Cola",
    }


@app.get("/pedido/{id_pedido}")
def obtener_pedido(id_pedido: int):
    """Respaldo por polling para cuando el WebSocket no está disponible."""
    try:
        snap = snapshot_pedido(id_pedido)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    if snap is None:
        raise HTTPException(status_code=404, detail="Pedido no encontrado")
    return snap


# ---------------------------------------------------------------------------
# RUTAS - COCINA (KDS)
# ---------------------------------------------------------------------------
@app.get("/pedidos_activos")
def obtener_pedidos_activos():
    try:
        return {"pedidos": pedidos_activos_db()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/pedido/{id_pedido}/estado")
async def actualizar_estado_pedido(id_pedido: int, estado_req: ActualizarEstado):
    try:
        resultado = await run_in_threadpool(
            cambiar_estado_db, id_pedido, estado_req.nuevo_estado
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if resultado["cambio"]:
        await propagar_cambios()  # <- aquí el celular del alumno se entera
    return {
        "mensaje": f"Pedido {id_pedido} actualizado a {resultado['nuevo']}",
        "estado_anterior": resultado["anterior"],
        "estado": resultado["nuevo"],
    }


@app.get("/admin", include_in_schema=False)
def panel_cocina():
    """Sirve el KDS desde el mismo servidor: abre http://<IP>:8000/admin"""
    return FileResponse(Path(__file__).with_name("admin.html"))
