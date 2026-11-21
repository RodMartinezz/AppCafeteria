"""
Pruebas del flujo en tiempo real SIN necesidad de MySQL (la capa de datos se
reemplaza por un diccionario en memoria).

Ejecutar desde backend_api:
    pip install pytest httpx
    python -m pytest test_tiempo_real.py -v
"""
import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import main


class BDFalsa:
    """Imita las 3 funciones de datos que usan los endpoints."""

    def __init__(self):
        self.pedidos = {}
        self.sig = 1

    def snapshot(self, id_pedido):
        p = self.pedidos.get(id_pedido)
        if not p:
            return None
        antes = 0
        if p["estado"] == "En Cola":
            antes = sum(
                1
                for o in self.pedidos.values()
                if o["estado"] in ("En Cola", "Preparando") and o["id_pedido"] < id_pedido
            )
        return {**p, "items": [{"cantidad": 1, "notas": "", "nombre": "Torta"}], "pedidos_antes": antes}

    def crear(self, pedido):
        id_pedido = self.sig
        self.sig += 1
        self.pedidos[id_pedido] = {
            "id_pedido": id_pedido,
            "nombre_estudiante": pedido.nombre_estudiante,
            "matricula": pedido.matricula,
            "estado": "En Cola",
            "total": 45.5,
            "metodo_pago": pedido.metodo_pago,
            "fecha_hora": "2026-11-18T12:00:00",
        }
        return {"id_pedido": id_pedido, "total": 45.5}

    def cambiar(self, id_pedido, nuevo):
        p = self.pedidos.get(id_pedido)
        if not p:
            raise HTTPException(status_code=404, detail="Pedido no encontrado")
        anterior = p["estado"]
        if not main.transicion_valida(anterior, nuevo):
            raise HTTPException(status_code=409, detail="transición inválida")
        p["estado"] = nuevo
        return {"anterior": anterior, "nuevo": nuevo, "cambio": anterior != nuevo}


@pytest.fixture()
def cliente(monkeypatch):
    bd = BDFalsa()
    monkeypatch.setattr(main, "snapshot_pedido", bd.snapshot)
    monkeypatch.setattr(main, "crear_pedido_db", bd.crear)
    monkeypatch.setattr(main, "cambiar_estado_db", bd.cambiar)
    main.gestor.por_pedido.clear()
    main.gestor.cocina.clear()
    # Las rutas de cocina/admin exigen el token de administrador
    with TestClient(main.app, headers={"X-Admin-Token": main.ADMIN_TOKEN}) as c:
        yield c


PEDIDO = {
    "nombre_estudiante": "Ana",
    "matricula": "12345",
    "metodo_pago": "Efectivo",
    "items": [{"id_producto": 1, "cantidad": 1, "notas": ""}],
}


def test_alumno_recibe_cada_cambio_de_estado(cliente):
    numero = cliente.post("/ordenar", json=PEDIDO).json()["numero_orden"]

    with cliente.websocket_connect(f"/ws/pedido/{numero}") as ws:
        assert ws.receive_json()["pedido"]["estado"] == "En Cola"

        for estado in ("Preparando", "Listo", "Entregado"):
            r = cliente.put(f"/pedido/{numero}/estado", json={"nuevo_estado": estado})
            assert r.status_code == 200
            msg = ws.receive_json()
            assert msg["tipo"] == "estado"
            assert msg["pedido"]["estado"] == estado


def test_cocina_se_entera_de_pedido_nuevo_y_de_cambios(cliente):
    with cliente.websocket_connect(f"/ws/cocina?token={main.ADMIN_TOKEN}") as cocina:
        numero = cliente.post("/ordenar", json=PEDIDO).json()["numero_orden"]
        assert cocina.receive_json() == {"tipo": "actualizar"}
        cliente.put(f"/pedido/{numero}/estado", json={"nuevo_estado": "Preparando"})
        assert cocina.receive_json() == {"tipo": "actualizar"}


def test_estado_invalido_o_salto_de_estado_se_rechaza(cliente):
    numero = cliente.post("/ordenar", json=PEDIDO).json()["numero_orden"]
    assert cliente.put(f"/pedido/{numero}/estado", json={"nuevo_estado": "Cualquier cosa"}).status_code == 422
    # De 'En Cola' no se puede saltar directo a 'Listo'
    assert cliente.put(f"/pedido/{numero}/estado", json={"nuevo_estado": "Listo"}).status_code == 409
    assert cliente.put("/pedido/999/estado", json={"nuevo_estado": "Preparando"}).status_code == 404


def test_cocina_exige_token(cliente):
    sin_token = TestClient(main.app)
    assert sin_token.get("/pedidos_activos").status_code == 401
    assert sin_token.put("/pedido/1/estado", json={"nuevo_estado": "Preparando"}).status_code == 401
    with cliente.websocket_connect("/ws/cocina?token=incorrecto") as ws:
        with pytest.raises(Exception) as exc:
            ws.receive_json()
        assert getattr(exc.value, "code", None) == 4401


def test_polling_de_respaldo(cliente):
    numero = cliente.post("/ordenar", json=PEDIDO).json()["numero_orden"]
    assert cliente.get(f"/pedido/{numero}").json()["estado"] == "En Cola"
    cliente.put(f"/pedido/{numero}/estado", json={"nuevo_estado": "Preparando"})
    assert cliente.get(f"/pedido/{numero}").json()["estado"] == "Preparando"
    assert cliente.get("/pedido/999").status_code == 404


def test_pedido_inexistente_cierra_con_4404(cliente):
    with cliente.websocket_connect("/ws/pedido/999") as ws:
        assert ws.receive_json()["tipo"] == "error"
        with pytest.raises(Exception) as exc:
            ws.receive_json()
        assert getattr(exc.value, "code", None) == 4404


def test_posicion_en_cola_se_actualiza_para_el_segundo_pedido(cliente):
    primero = cliente.post("/ordenar", json=PEDIDO).json()["numero_orden"]
    segundo = cliente.post("/ordenar", json=PEDIDO).json()["numero_orden"]

    with cliente.websocket_connect(f"/ws/pedido/{segundo}") as ws:
        assert ws.receive_json()["pedido"]["pedidos_antes"] == 1
        # Cuando el primer pedido sale de la cola, el segundo ve que ya no hay nadie antes
        cliente.put(f"/pedido/{primero}/estado", json={"nuevo_estado": "Preparando"})
        assert ws.receive_json()["pedido"]["pedidos_antes"] == 1  # 'Preparando' aún cuenta
        cliente.put(f"/pedido/{primero}/estado", json={"nuevo_estado": "Listo"})
        assert ws.receive_json()["pedido"]["pedidos_antes"] == 0


def test_validacion_de_pedido_nuevo(cliente):
    malo = {**PEDIDO, "items": []}
    assert cliente.post("/ordenar", json=malo).status_code == 422
    malo = {**PEDIDO, "metodo_pago": "Bitcoin"}
    assert cliente.post("/ordenar", json=malo).status_code == 422
