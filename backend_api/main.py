from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List
import mysql.connector

app = FastAPI(title="Cafetería UMG - Base de Datos Real")

# Configuración de CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- CONFIGURACIÓN DE DB (Ajusta con tus datos de MySQL) ---
def get_db_connection():
    return mysql.connector.connect(
        host="localhost",
        user="root",      # Tu usuario de MySQL
        password="",      # Tu contraseña (deja vacío si usas XAMPP)
        database="cafeteria_umg"
    )

# --- MODELOS ---
class ItemPedido(BaseModel):
    id_producto: int
    cantidad: int
    notas: str = ""

class NuevoPedido(BaseModel):
    nombre_estudiante: str
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
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. Calcular el total primero
        total = 0
        for item in pedido.items:
            cursor.execute("SELECT precio FROM Productos WHERE id_producto = %s", (item.id_producto,))
            precio = cursor.fetchone()[0]
            total += precio * item.cantidad
        
        # 2. Insertar en tabla Pedidos
        sql_pedido = "INSERT INTO Pedidos (nombre_estudiante, total) VALUES (%s, %s)"
        cursor.execute(sql_pedido, (pedido.nombre_estudiante, total))
        id_pedido = cursor.lastrowid
        
        # 3. Insertar detalles
        sql_detalle = "INSERT INTO Detalle_Pedidos (id_pedido, id_producto, cantidad, notas) VALUES (%s, %s, %s, %s)"
        for item in pedido.items:
            cursor.execute(sql_detalle, (id_pedido, item.id_producto, item.cantidad, item.notas))
            
        conn.commit()
        cursor.close()
        conn.close()
        return {"mensaje": "Pedido guardado en DB", "numero_orden": id_pedido}
    except Exception as e:
        if conn: conn.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/cocina/pendientes")
def ver_pendientes():
    conn = get_db_connection()
    cursor = conn.cursor(dictionary=True)
    # Traemos pedidos que no han sido entregados
    cursor.execute("SELECT * FROM Pedidos WHERE estado != 'Entregado' ORDER BY fecha_hora ASC")
    pendientes = cursor.fetchall()
    cursor.close()
    conn.close()
    return {"pendientes": pendientes}

@app.put("/cocina/listo/{id_pedido}")
def marcar_listo(id_pedido: int):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("UPDATE Pedidos SET estado = 'Listo' WHERE id_pedido = %s", (id_pedido,))
    conn.commit()
    cursor.close()
    conn.close()
    return {"mensaje": "Pedido actualizado"}