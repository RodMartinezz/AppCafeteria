from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import List

app = FastAPI(title="Cafetería UMG API V1")

# Permite que el celular se conecte sin bloqueos
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- MODELOS DE DATOS ---
class ItemPedido(BaseModel):
    id_producto: int
    cantidad: int

class NuevoPedido(BaseModel):
    nombre_estudiante: str
    items: List[ItemPedido]

# --- MENÚ SIMULADO (Basado en tu Excel real) ---
menu_db = [
    {"id_producto": 1, "nombre": "Agua fresca 1Lt", "precio": 30.0},
    {"id_producto": 2, "nombre": "Café americano", "precio": 35.0},
    {"id_producto": 3, "nombre": "Brownies", "precio": 40.0},
    {"id_producto": 4, "nombre": "Doritos", "precio": 25.0},
    {"id_producto": 5, "nombre": "Waffles", "precio": 25.0},
    {"id_producto": 6, "nombre": "Vasito salchichas", "precio": 15.0},
    {"id_producto": 7, "nombre": "Jericalla", "precio": 27.0},
    {"id_producto": 8, "nombre": "Pan de elote vegano", "precio": 48.0},
    {"id_producto": 9, "nombre": "Electrolit varios", "precio": 28.0},
    {"id_producto": 10, "nombre": "Kinder Delice", "precio": 16.0},
    {"id_producto": 11, "nombre": "Pay de Limon", "precio": 40.0},
    {"id_producto": 12, "nombre": "Vasito de fruta", "precio": 25.0}
]

# Variables para guardar las órdenes temporalmente
pedidos_db = []
contador_ordenes = 1

# --- RUTAS DE LA API ---
@app.get("/")
def inicio():
    return {"mensaje": "API de Cafetería UMG en línea"}

@app.get("/menu")
def obtener_menu():
    """Envía el menú de tu Excel al celular"""
    return {"menu": menu_db}

@app.post("/ordenar")
def crear_pedido(pedido: NuevoPedido):
    """Recibe la orden del celular y calcula el total"""
    global contador_ordenes
    total = 0
    
    # Buscamos los precios para sumar el total
    for item in pedido.items:
        producto = next((p for p in menu_db if p["id_producto"] == item.id_producto), None)
        if producto:
            total += producto["precio"] * item.cantidad
            
    # Guardamos el ticket
    nueva_orden = {
        "id_pedido": contador_ordenes,
        "estudiante": pedido.nombre_estudiante,
        "total": total,
        "estado": "En Cola",
        "items": pedido.items
    }
    pedidos_db.append(nueva_orden)
    
    numero_actual = contador_ordenes
    contador_ordenes += 1
    
    return {"mensaje": "Pedido recibido", "numero_orden": numero_actual}