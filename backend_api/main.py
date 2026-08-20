from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import mysql.connector

app = FastAPI(title="Cafetería UMG - API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",
        password="",
        database="cafeteria_umg"
    )

# --- MODELOS ---
class ItemPedido(BaseModel):
    id_producto: int
    cantidad: int
    notas: str = ""

class NuevoPedido(BaseModel):
    nombre_estudiante: str
    matricula: str
    metodo_pago: str  # 'Efectivo' o 'Tarjeta'
    items: List[ItemPedido]

# --- RUTAS ---
@app.get("/menu")
def obtener_menu():
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM Productos WHERE disponible = TRUE")
        menu = cursor.fetchall()
        cursor.close()
        conn.close()
        return {"menu": menu}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/ordenar")
def crear_pedido(pedido: NuevoPedido):
    conn = None
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Calcular el total
        total = 0.0
        for item in pedido.items:
            cursor.execute("SELECT precio FROM Productos WHERE id_producto = %s", (item.id_producto,))
            fila = cursor.fetchone()
            if not fila:
                raise HTTPException(status_code=400, detail=f"Producto con ID {item.id_producto} no encontrado")
            total += float(fila[0]) * item.cantidad
        
        # 2. Insertar en Pedidos
        sql_pedido = "INSERT INTO Pedidos (nombre_estudiante, matricula, total, metodo_pago) VALUES (%s, %s, %s, %s)"
        cursor.execute(sql_pedido, (pedido.nombre_estudiante, pedido.matricula, total, pedido.metodo_pago))
        id_pedido = cursor.lastrowid
        
        # 3. Insertar detalles
        sql_detalle = "INSERT INTO Detalle_Pedidos (id_pedido, id_producto, cantidad, notas) VALUES (%s, %s, %s, %s)"
        for item in pedido.items:
            cursor.execute(sql_detalle, (id_pedido, item.id_producto, item.cantidad, item.notas))
            
        conn.commit()
        cursor.close()
        conn.close()
        return {"mensaje": "Pedido registrado", "numero_orden": id_pedido, "total": total}
    except Exception as e:
        if conn and conn.is_connected():
            conn.rollback()
            conn.close()
        raise HTTPException(status_code=500, detail=str(e))