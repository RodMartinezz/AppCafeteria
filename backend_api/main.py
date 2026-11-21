"""
Cafetería UMG - API

Alumnos (públicas):  GET /menu · POST /ordenar · GET /pedido/{id} · WS /ws/pedido/{id}
Cocina / admin (requieren el token de administrador, ver ADMIN_TOKEN):
    GET /pedidos_activos · PUT /pedido/{id}/estado · WS /ws/cocina?token=...
    /admin/productos ... (catálogo + importación Excel/CSV)
    /admin/historial ... (pedidos pasados, ranking, CSV)
El panel web se sirve en  GET /admin  (archivos estáticos en /admin_static).

Requiere:  pip install -r requirements.txt   ('uvicorn[standard]' trae 'websockets')
"""
import asyncio
import csv
import io
import os
import secrets
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from pathlib import Path
from typing import Dict, List, Literal, Optional, Set

from fastapi import (
    APIRouter,
    Depends,
    FastAPI,
    File,
    Header,
    HTTPException,
    Query,
    UploadFile,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.concurrency import run_in_threadpool
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

import admin_db
import catalogo
from db import db
from modelos import ConfirmarImportacion, ProductoEditar, ProductoNuevo

CARPETA = Path(__file__).parent

# ---------------------------------------------------------------------------
# SEGURIDAD: token del panel de administración
# ---------------------------------------------------------------------------
# Cámbialo antes de usar la app de verdad:   set ADMIN_TOKEN=mi-clave-larga   (Windows)
ADMIN_TOKEN = os.environ.get("ADMIN_TOKEN", "umg-cocina")


def token_valido(token: Optional[str]) -> bool:
    return bool(token) and secrets.compare_digest(token.encode(), ADMIN_TOKEN.encode())


def requiere_admin(x_admin_token: Optional[str] = Header(default=None)) -> None:
    if not token_valido(x_admin_token):
        raise HTTPException(status_code=401, detail="Token de administrador inválido o ausente")


# ---------------------------------------------------------------------------
# ARRANQUE: avisa si falta correr la migración
# ---------------------------------------------------------------------------
def verificar_esquema() -> List[str]:
    """Lista de problemas del esquema (vacía si todo está bien)."""
    falta = []
    with db() as (_, cur):
        for tabla, columna in (
            ("Productos", "nombre_norm"),
            ("Detalle_Pedidos", "precio_unitario"),
            ("Detalle_Pedidos", "nombre_producto"),
        ):
            cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
                "AND LOWER(TABLE_NAME) = LOWER(%s) AND COLUMN_NAME = %s",
                (tabla, columna),
            )
            if cur.fetchone()["n"] == 0:
                falta.append(f"{tabla}.{columna}")
    return falta


@asynccontextmanager
async def lifespan(_: FastAPI):
    try:
        falta = await run_in_threadpool(verificar_esquema)
        if falta:
            print(
                "\n⚠⚠  FALTA LA MIGRACIÓN DE LA BD (columnas: " + ", ".join(falta) + ").\n"
                "    Ejecuta:  python migracion_catalogo.py\n"
            )
    except Exception as e:  # MySQL apagado: el servidor arranca igual
        print(f"⚠ No se pudo verificar la BD al arrancar: {e}")
    if ADMIN_TOKEN == "umg-cocina":
        print("⚠ Usando el token de administrador por defecto. Define la variable ADMIN_TOKEN.")
    yield


app = FastAPI(title="Cafetería UMG - API", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

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
# CAPA DE DATOS DE PEDIDOS (síncrona; los endpoints las llaman en un hilo)
# ---------------------------------------------------------------------------
def _items_de_pedidos(cursor, ids: List[int]) -> Dict[int, list]:
    if not ids:
        return {}
    marcadores = ",".join(["%s"] * len(ids))
    cursor.execute(
        f"""
        SELECT d.id_pedido, d.cantidad, d.notas,
               COALESCE(d.nombre_producto, p.nombre) AS nombre
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
            f"SELECT id_producto, nombre, precio FROM Productos "
            f"WHERE disponible = TRUE AND id_producto IN ({marcadores})",
            tuple(ids),
        )
        productos = {f["id_producto"]: f for f in cursor.fetchall()}

        faltantes = [i for i in ids if i not in productos]
        if faltantes:
            raise HTTPException(
                status_code=400,
                detail="Algún producto ya no está disponible. Actualiza el menú e inténtalo de nuevo.",
            )

        total = sum(Decimal(productos[i.id_producto]["precio"]) * i.cantidad for i in pedido.items)

        # El precio que vio el alumno ya no coincide (el admin lo cambió mientras ordenaba)
        if pedido.total_esperado is not None and abs(total - Decimal(str(pedido.total_esperado))) > Decimal("0.005"):
            raise HTTPException(
                status_code=409,
                detail=f"Los precios del menú cambiaron (ahora el total es ${total:.2f}). Revisa tu pedido.",
            )

        cursor.execute(
            "INSERT INTO Pedidos (nombre_estudiante, matricula, total, metodo_pago) "
            "VALUES (%s, %s, %s, %s)",
            (pedido.nombre_estudiante, pedido.matricula, total, pedido.metodo_pago),
        )
        id_pedido = cursor.lastrowid

        # Se guarda nombre y precio de ESTA venta: editar el producto después no cambia el historial
        for item in pedido.items:
            p = productos[item.id_producto]
            cursor.execute(
                "INSERT INTO Detalle_Pedidos "
                "(id_pedido, id_producto, cantidad, notas, nombre_producto, precio_unitario) "
                "VALUES (%s, %s, %s, %s, %s, %s)",
                (id_pedido, item.id_producto, item.cantidad, item.notas, p["nombre"], p["precio"]),
            )
    return {"id_pedido": id_pedido, "total": float(total)}


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
async def ws_cocina(websocket: WebSocket, token: Optional[str] = Query(default=None)):
    await websocket.accept()
    if not token_valido(token):
        await websocket.close(code=4401)  # 4401: token inválido (el panel pide la clave de nuevo)
        return
    gestor.cocina.add(websocket)
    try:
        await _mantener_abierto(websocket)
    except (WebSocketDisconnect, RuntimeError):
        pass
    finally:
        gestor.cocina.discard(websocket)


# ---------------------------------------------------------------------------
# MODELOS DE PEDIDOS
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
    # Total que el alumno vio en pantalla: si el servidor calcula otro, se rechaza con 409
    total_esperado: Optional[float] = Field(default=None, ge=0)


class ActualizarEstado(BaseModel):
    nuevo_estado: Estado


# ---------------------------------------------------------------------------
# RUTAS - ALUMNOS (públicas)
# ---------------------------------------------------------------------------
@app.get("/menu")
def obtener_menu():
    try:
        with db() as (_, cursor):
            cursor.execute(
                "SELECT id_producto, nombre, precio, categoria, tipo_preparacion "
                "FROM Productos WHERE disponible = TRUE ORDER BY categoria, nombre"
            )
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
# RUTAS - COCINA (KDS) · requieren token
# ---------------------------------------------------------------------------
@app.get("/pedidos_activos", dependencies=[Depends(requiere_admin)])
def obtener_pedidos_activos():
    try:
        return {"pedidos": pedidos_activos_db()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/pedido/{id_pedido}/estado", dependencies=[Depends(requiere_admin)])
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


# ---------------------------------------------------------------------------
# RUTAS - ADMINISTRACIÓN: catálogo, importación, historial · requieren token
# ---------------------------------------------------------------------------
admin = APIRouter(prefix="/admin", dependencies=[Depends(requiere_admin)])


async def _en_hilo(funcion, *args):
    """Ejecuta la función de BD en un hilo; los errores inesperados salen como 500."""
    try:
        return await run_in_threadpool(funcion, *args)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@admin.get("/productos")
async def admin_listar_productos(
    q: Optional[str] = None,
    categoria: Optional[Literal["Comida", "Bebida"]] = None,
    disponible: Optional[bool] = None,
):
    return {"productos": await _en_hilo(admin_db.listar_productos, q, categoria, disponible)}


@admin.post("/productos", status_code=201)
async def admin_crear_producto(producto: ProductoNuevo):
    return await _en_hilo(admin_db.crear_producto, producto)


@admin.put("/productos/{id_producto}")
async def admin_editar_producto(id_producto: int, cambios: ProductoEditar):
    return await _en_hilo(admin_db.editar_producto, id_producto, cambios)


@admin.get("/productos/{id_producto}/precios")
async def admin_historial_precios(id_producto: int):
    return {"cambios": await _en_hilo(admin_db.historial_precios_producto, id_producto)}


@admin.post("/productos/importar/previsualizar")
async def admin_importar_previsualizar(archivo: UploadFile = File(...)):
    """Paso 1: lee el Excel/CSV y dice qué pasaría con cada fila. NO modifica la BD."""
    contenido = await archivo.read(catalogo.MAX_BYTES + 1)
    try:
        leido = await run_in_threadpool(catalogo.leer_archivo, archivo.filename or "", contenido)
    except catalogo.ErrorArchivo as e:
        raise HTTPException(status_code=400, detail=str(e))
    actuales = await _en_hilo(admin_db.catalogo_para_importar)
    analisis = catalogo.analizar_filas(leido["filas"], actuales)
    return {
        "archivo": archivo.filename,
        "hoja": leido["hoja"],
        "columnas": leido["columnas"],
        "advertencias": leido["advertencias"],
        **analisis,
    }


@admin.post("/productos/importar/confirmar")
async def admin_importar_confirmar(req: ConfirmarImportacion):
    """Paso 2: aplica SOLO las filas que el admin dejó marcadas (todo o nada)."""
    return await _en_hilo(admin_db.aplicar_importacion, req)


def filtros_historial(
    desde: Optional[date] = None,
    hasta: Optional[date] = None,
    estado: Optional[Estado] = None,
    matricula: Optional[str] = None,
    producto: Optional[str] = None,
    metodo_pago: Optional[Literal["Efectivo", "Tarjeta"]] = None,
    id_pedido: Optional[int] = None,
) -> admin_db.FiltrosHistorial:
    return admin_db.FiltrosHistorial(desde, hasta, estado, matricula, producto, metodo_pago, id_pedido)


@admin.get("/historial")
async def admin_historial(
    f: admin_db.FiltrosHistorial = Depends(filtros_historial),
    limite: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
):
    return await _en_hilo(admin_db.listar_historial, f, limite, offset)


@admin.get("/historial/productos")
async def admin_ranking_productos(
    f: admin_db.FiltrosHistorial = Depends(filtros_historial),
    limite: int = Query(default=15, ge=1, le=100),
):
    return {"productos": await _en_hilo(admin_db.ranking_productos, f, limite)}


def _celda_segura(valor) -> str:
    """Evita la 'inyección de fórmulas' al abrir el CSV en Excel (=, +, -, @)."""
    texto = "" if valor is None else str(valor)
    return "'" + texto if texto[:1] in ("=", "+", "-", "@", "\t", "\r") else texto


@admin.get("/historial/exportar.csv")
async def admin_exportar_historial(f: admin_db.FiltrosHistorial = Depends(filtros_historial)):
    pedidos = await _en_hilo(admin_db.pedidos_para_exportar, f)
    salida = io.StringIO()
    escritor = csv.writer(salida)
    escritor.writerow(
        ["Pedido", "Fecha", "Estudiante", "Matrícula", "Estado", "Pago", "Total", "Productos"]
    )
    for p in pedidos:
        productos = "; ".join(f"{i['cantidad']}x {i['nombre']}" for i in p["items"])
        escritor.writerow(
            [
                p["id_pedido"],
                p["fecha_hora"].strftime("%Y-%m-%d %H:%M:%S") if p["fecha_hora"] else "",
                _celda_segura(p["nombre_estudiante"]),
                _celda_segura(p["matricula"]),
                p["estado"],
                p["metodo_pago"] or "",
                f"{Decimal(p['total']):.2f}",
                _celda_segura(productos),
            ]
        )
    # BOM para que Excel abra bien los acentos
    return Response(
        content="﻿" + salida.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="historial_pedidos.csv"'},
    )


app.include_router(admin)


# ---------------------------------------------------------------------------
# PANEL WEB (HTML + JS estáticos; los datos siempre pasan por la API con token)
# ---------------------------------------------------------------------------
class StaticSinCache(StaticFiles):
    """Evita que el navegador use un JS viejo mientras desarrollas."""

    async def get_response(self, path, scope):
        respuesta = await super().get_response(path, scope)
        respuesta.headers["Cache-Control"] = "no-cache"
        return respuesta


(CARPETA / "admin_static").mkdir(exist_ok=True)
app.mount("/admin_static", StaticSinCache(directory=CARPETA / "admin_static"), name="admin_static")


@app.get("/admin", include_in_schema=False)
def panel_admin():
    """Abre http://<IP>:8000/admin"""
    return FileResponse(CARPETA / "admin.html", headers={"Cache-Control": "no-cache"})
