"""
Pruebas CONTRA MySQL/MariaDB REAL (catálogo, importación, historial).

Usan una base de datos aparte, `cafeteria_umg_test`, que se borra y recrea sola:
tu base real NO se toca. Si no hay servidor de BD disponible, se omiten.

    cd backend_api
    python -m pytest test_catalogo_mysql.py -v

Variables opcionales: DB_HOST, DB_PORT, DB_USER, DB_PASSWORD (por defecto localhost/root/sin clave)
y EXCEL_PRODUCTOS=<ruta a tu Lista_Productos.xlsx> para probar también con tu archivo real.
"""
import io
import os
from pathlib import Path

import mysql.connector
import openpyxl
import pytest
from fastapi.testclient import TestClient

import db as modulo_db
import main
import migracion_catalogo

BACKEND = Path(__file__).parent
BD_PRUEBAS = "cafeteria_umg_test"
CT_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _conectar(base=None):
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        port=int(os.environ.get("DB_PORT", "3306")),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=base,
        autocommit=True,
    )


@pytest.fixture(scope="module")
def bd():
    try:
        admin = _conectar()
    except Exception as e:
        pytest.skip(f"No hay servidor MySQL/MariaDB disponible: {e}")
    cur = admin.cursor()
    cur.execute(f"DROP DATABASE IF EXISTS {BD_PRUEBAS}")
    cur.execute(f"CREATE DATABASE {BD_PRUEBAS} CHARACTER SET utf8mb4")

    anterior = os.environ.get("DB_NAME")
    os.environ["DB_NAME"] = BD_PRUEBAS
    modulo_db.reset_pool()

    con = _conectar(BD_PRUEBAS)
    c = con.cursor()
    for sentencia in (BACKEND / "bd.sql").read_text(encoding="utf-8").split(";"):
        if sentencia.strip():
            c.execute(sentencia)
    con.close()
    assert migracion_catalogo.migrar() == 0
    yield
    modulo_db.reset_pool()
    if anterior is None:
        os.environ.pop("DB_NAME", None)
    else:
        os.environ["DB_NAME"] = anterior
    cur.execute(f"DROP DATABASE IF EXISTS {BD_PRUEBAS}")
    admin.close()


@pytest.fixture()
def api(bd):
    con = _conectar(BD_PRUEBAS)
    c = con.cursor()
    c.execute("SET FOREIGN_KEY_CHECKS = 0")
    for t in ("Historial_Precios", "Detalle_Pedidos", "Pedidos", "Productos"):
        c.execute(f"TRUNCATE TABLE {t}")
    c.execute("SET FOREIGN_KEY_CHECKS = 1")
    con.close()
    main.gestor.por_pedido.clear()
    main.gestor.cocina.clear()
    with TestClient(main.app, headers={"X-Admin-Token": main.ADMIN_TOKEN}) as cliente:
        yield cliente


def crear(api, nombre, precio, categoria="Comida", **extra):
    r = api.post("/admin/productos", json={"nombre": nombre, "precio": precio, "categoria": categoria, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def ordenar(api, items, **extra):
    cuerpo = {
        "nombre_estudiante": "Ana",
        "matricula": "12345",
        "metodo_pago": "Efectivo",
        "items": items,
        **extra,
    }
    return api.post("/ordenar", json=cuerpo)


def xlsx(filas, encabezado=("Productos", "Precios")):
    wb = openpyxl.Workbook()
    ws = wb.active
    if encabezado:
        ws.append(list(encabezado))
    for f in filas:
        ws.append(list(f))
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def previsualizar(api, contenido, nombre="lista.xlsx"):
    r = api.post("/admin/productos/importar/previsualizar", files={"archivo": (nombre, contenido, CT_XLSX)})
    return r


def confirmar_todo(api, vista, **opciones):
    """Confirma exactamente lo que la vista previa dejó marcado como 'incluir'."""
    filas = [
        {k: f[k] for k in ("nombre", "precio", "categoria", "tipo_preparacion")}
        for f in vista["filas"]
        if f["incluir"]
    ]
    return api.post(
        "/admin/productos/importar/confirmar",
        json={"filas": filas, "claves_archivo": vista["claves_archivo"], **opciones},
    )


# ---------------------------------------------------------------------------
# MIGRACIÓN Y SEGURIDAD
# ---------------------------------------------------------------------------
def test_migracion_es_idempotente(bd):
    assert migracion_catalogo.migrar() == 0
    assert migracion_catalogo.migrar() == 0
    assert main.verificar_esquema() == []


def test_rutas_admin_exigen_token(api):
    sin = TestClient(main.app)
    assert sin.get("/admin/productos").status_code == 401
    assert sin.post("/admin/productos", json={}).status_code == 401
    assert sin.get("/admin/historial").status_code == 401
    assert sin.post("/admin/productos/importar/confirmar", json={}).status_code == 401
    assert sin.get("/menu").status_code == 200  # el menú de los alumnos sí es público
    mal = TestClient(main.app, headers={"X-Admin-Token": "otra"})
    assert mal.get("/admin/productos").status_code == 401


# ---------------------------------------------------------------------------
# CATÁLOGO
# ---------------------------------------------------------------------------
def test_crear_y_listar_productos(api):
    p = crear(api, "  Café   Americano ", 35, "Bebida")
    assert p["nombre"] == "Café Americano" and p["precio"] == 35 and p["disponible"] is True
    lista = api.get("/admin/productos").json()["productos"]
    assert [x["nombre"] for x in lista] == ["Café Americano"]
    # búsqueda sin acentos ni mayúsculas
    assert len(api.get("/admin/productos", params={"q": "CAFE"}).json()["productos"]) == 1
    assert api.get("/admin/productos", params={"q": "torta"}).json()["productos"] == []


def test_no_permite_duplicados_ni_datos_invalidos(api):
    crear(api, "Café americano", 35, "Bebida")
    r = api.post("/admin/productos", json={"nombre": " CAFÉ  AMERICANO ", "precio": 40, "categoria": "Bebida"})
    assert r.status_code == 409
    for precio in (0, -5, 12.345, 100000):
        r = api.post("/admin/productos", json={"nombre": f"X{precio}", "precio": precio, "categoria": "Comida"})
        assert r.status_code == 422, precio
    assert api.post("/admin/productos", json={"nombre": "   ", "precio": 5, "categoria": "Comida"}).status_code == 422
    assert api.post("/admin/productos", json={"nombre": "Y", "precio": 5, "categoria": "Postre"}).status_code == 422


def test_editar_precio_categoria_y_renombrar(api):
    p = crear(api, "Torta", 45)
    otro = crear(api, "Sandwich", 30)
    r = api.put(f"/admin/productos/{p['id_producto']}", json={"precio": 50, "categoria": "Comida", "tipo_preparacion": "Parrilla"})
    assert r.status_code == 200 and r.json()["precio"] == 50 and r.json()["tipo_preparacion"] == "Parrilla"
    # renombrar a un nombre ya usado -> 409
    assert api.put(f"/admin/productos/{p['id_producto']}", json={"nombre": "sándwich"}).status_code == 409
    # renombrarse a sí mismo con otra capitalización está permitido
    assert api.put(f"/admin/productos/{p['id_producto']}", json={"nombre": "TORTA"}).status_code == 200
    assert api.put("/admin/productos/9999", json={"precio": 5}).status_code == 404
    assert api.put(f"/admin/productos/{otro['id_producto']}", json={}).status_code == 422
    hist = api.get(f"/admin/productos/{p['id_producto']}/precios").json()["cambios"]
    assert [(h["precio_anterior"], h["precio_nuevo"], h["origen"]) for h in hist] == [(45, 50, "manual"), (None, 45, "creacion")]


def test_cambiar_precio_o_desactivar_no_rompe_el_historial(api):
    cafe = crear(api, "Café", 30, "Bebida")
    id_cafe = cafe["id_producto"]
    r = ordenar(api, [{"id_producto": id_cafe, "cantidad": 2}])
    assert r.status_code == 200 and r.json()["total"] == 60
    id_pedido = r.json()["numero_orden"]

    # El admin sube el precio y luego retira el producto del menú
    assert api.put(f"/admin/productos/{id_cafe}", json={"precio": 40}).status_code == 200
    assert api.put(f"/admin/productos/{id_cafe}", json={"disponible": False}).status_code == 200

    # El pedido viejo conserva lo que se cobró ese día
    h = api.get("/admin/historial").json()
    assert h["total_pedidos"] == 1 and float(h["ventas"]) == 60
    item = h["pedidos"][0]["items"][0]
    assert item["nombre"] == "Café" and float(item["precio_unitario"]) == 30 and item["cantidad"] == 2
    assert api.get(f"/pedido/{id_pedido}").json()["items"][0]["nombre"] == "Café"

    # Y ya no se puede pedir ni aparece en el menú de los alumnos
    assert api.get("/menu").json()["menu"] == []
    r = ordenar(api, [{"id_producto": id_cafe, "cantidad": 1}])
    assert r.status_code == 400 and "disponible" in r.json()["detail"]

    # Reactivar con el precio nuevo
    api.put(f"/admin/productos/{id_cafe}", json={"disponible": True})
    assert float(api.get("/menu").json()["menu"][0]["precio"]) == 40
    assert ordenar(api, [{"id_producto": id_cafe}]).json()["total"] == 40


def test_menu_solo_muestra_disponibles(api):
    crear(api, "Visible", 10)
    crear(api, "Oculto", 10, disponible=False)
    assert [p["nombre"] for p in api.get("/menu").json()["menu"]] == ["Visible"]


def test_pedido_rechaza_si_el_precio_cambio(api):
    p = crear(api, "Torta", 45)
    i = p["id_producto"]
    api.put(f"/admin/productos/{i}", json={"precio": 50})
    r = ordenar(api, [{"id_producto": i, "cantidad": 1}], total_esperado=45)
    assert r.status_code == 409 and "precios" in r.json()["detail"].lower()
    assert api.get("/admin/historial").json()["total_pedidos"] == 0  # no se creó nada
    assert ordenar(api, [{"id_producto": i, "cantidad": 1}], total_esperado=50).status_code == 200


# ---------------------------------------------------------------------------
# IMPORTACIÓN
# ---------------------------------------------------------------------------
def test_importar_excel_sintetico_completo(api):
    crear(api, "Café Americano", 30, "Bebida")  # ya existe con otro precio y con otra escritura
    contenido = xlsx(
        [
            ("cafe americano", 35),  # existe: sube a 35 (se conserva la categoría de la BD)
            ("Chetos  ", 20),  # espacios sobrantes
            ("Chetos", 20),  # duplicado exacto en el archivo
            ("Doritos", 25),
            ("Doritos", 27),  # mismo nombre, otro precio -> error
            ("Latte", "$35.00"),  # precio como texto
            ("Agua 1Lt", 20),
            ("Agua 1.5Lt", 22),  # presentaciones distintas: NO son typo
            ("Mazapan", 5),
            ("Mazapán", 5),  # mismo producto con acento -> duplicado
            ("Sin precio", None),
            ("Gratis", 0),
            ("Raro", "abc"),
            (None, 10),
            (None, None),  # fila en blanco: se ignora sin ruido
        ]
    )
    r = previsualizar(api, contenido)
    assert r.status_code == 200, r.text
    v = r.json()
    res = v["resumen"]
    por_linea = {f["linea"]: f for f in v["filas"]}
    assert por_linea[2]["accion"] == "actualizar_precio" and por_linea[2]["precio_actual"] == 30
    assert por_linea[3]["nombre"] == "Chetos" and por_linea[3]["accion"] == "crear"
    assert por_linea[4]["accion"] == "duplicado_ignorado"
    assert por_linea[6]["accion"] == "error" and "otro precio" in por_linea[6]["mensaje"]
    assert por_linea[7]["precio"] == 35 and por_linea[7]["categoria"] == "Bebida"
    assert por_linea[9]["accion"] == "crear"  # 1.5Lt no se confunde con 1Lt
    assert por_linea[11]["accion"] == "duplicado_ignorado"
    assert [por_linea[n]["accion"] for n in (12, 13, 14, 15)] == ["error"] * 4
    assert res["errores"] == 5 and res["duplicados_ignorados"] == 2 and res["cambian_precio"] == 1
    assert 16 not in por_linea  # fila en blanco

    # Vista previa NO modifica la BD
    assert len(api.get("/admin/productos").json()["productos"]) == 1

    c = confirmar_todo(api, v)
    assert c.status_code == 200, c.text
    assert c.json() == {"creados": 6, "actualizados": 1, "sin_cambios": 0, "desactivados": 0}
    nombres = {p["nombre"]: p for p in api.get("/admin/productos").json()["productos"]}
    assert nombres["Café Americano"]["precio"] == 35 and nombres["Café Americano"]["categoria"] == "Bebida"
    assert "Chetos" in nombres and "Chetos  " not in nombres

    # Repetir la misma importación no cambia nada ni duplica
    v2 = previsualizar(api, contenido).json()
    assert v2["resumen"]["nuevos"] == 0 and v2["resumen"]["cambian_precio"] == 0
    assert v2["resumen"]["sin_cambios"] == 7
    # No queda nada por aplicar: el servidor lo rechaza (el panel deshabilita el botón)
    assert confirmar_todo(api, v2).status_code == 422
    assert len(api.get("/admin/productos").json()["productos"]) == 7

    # El cambio de precio quedó en la bitácora con origen 'excel'
    pid = nombres["Café Americano"]["id_producto"]
    assert api.get(f"/admin/productos/{pid}/precios").json()["cambios"][0]["origen"] == "excel"


def test_importar_csv_con_punto_y_coma_y_cp1252(api):
    texto = "Producto;Precio;Categoría\nCafé;35,5;Bebida\nTorta jamón;45;Comida\n"
    r = api.post(
        "/admin/productos/importar/previsualizar",
        files={"archivo": ("lista.csv", texto.encode("cp1252"), "text/csv")},
    )
    assert r.status_code == 200, r.text
    v = r.json()
    assert [(f["nombre"], f["precio"], f["categoria"], f["categoria_inferida"]) for f in v["filas"]] == [
        ("Café", 35.5, "Bebida", False),
        ("Torta jamón", 45.0, "Comida", False),
    ]


def test_importar_archivo_invalido(api):
    for nombre, datos in (("a.xls", b"x"), ("a.txt.exe", b"x"), ("a.xlsx", b"no soy un zip"), ("a.csv", b"")):
        r = api.post("/admin/productos/importar/previsualizar", files={"archivo": (nombre, datos, "application/octet-stream")})
        assert r.status_code == 400, nombre
    grande = b"a" * (catalogo_max() + 10)
    assert api.post("/admin/productos/importar/previsualizar", files={"archivo": ("g.csv", grande, "text/csv")}).status_code == 400


def catalogo_max():
    import catalogo

    return catalogo.MAX_BYTES


def test_confirmar_valida_en_el_servidor(api):
    malo = {"filas": [{"nombre": "X", "precio": -1, "categoria": "Comida"}]}
    assert api.post("/admin/productos/importar/confirmar", json=malo).status_code == 422
    repetido = {"filas": [{"nombre": "Pan", "precio": 5, "categoria": "Comida"}, {"nombre": " pan ", "precio": 6, "categoria": "Comida"}]}
    assert api.post("/admin/productos/importar/confirmar", json=repetido).status_code == 400
    assert api.post("/admin/productos/importar/confirmar", json={"filas": []}).status_code == 422
    assert api.post("/admin/productos/importar/confirmar", json={"filas": [], "desactivar_faltantes": True}).status_code == 422
    assert api.get("/admin/productos").json()["productos"] == []  # nada se aplicó


def test_importar_es_todo_o_nada(api, monkeypatch):
    crear(api, "Existente", 10)
    cuerpo = {
        "filas": [
            {"nombre": "Nuevo 1", "precio": 5, "categoria": "Comida"},
            {"nombre": "Existente", "precio": 99, "categoria": "Comida"},
            {"nombre": "Nuevo 2", "precio": 6, "categoria": "Comida"},
        ]
    }
    # Fallo a mitad de la importación: se revierte TODO
    import admin_db

    original = admin_db.normalizar_nombre

    def explota(texto):
        if "Nuevo 2" in str(texto):
            raise RuntimeError("falla simulada")
        return original(texto)

    monkeypatch.setattr(admin_db, "normalizar_nombre", explota)
    r = api.post("/admin/productos/importar/confirmar", json=cuerpo)
    assert r.status_code == 500
    monkeypatch.undo()
    nombres = [p["nombre"] for p in api.get("/admin/productos").json()["productos"]]
    precios = {p["nombre"]: p["precio"] for p in api.get("/admin/productos").json()["productos"]}
    assert nombres == ["Existente"] and precios["Existente"] == 10


def test_opciones_de_importacion_actualizar_y_desactivar_faltantes(api):
    crear(api, "A", 10)
    crear(api, "B", 20)
    crear(api, "C", 30)
    v = previsualizar(api, xlsx([("A", 11), ("B", 20)])).json()
    assert v["resumen"]["faltantes_en_archivo"] == 1 and v["faltantes_en_archivo"] == ["C"]

    # No actualizar precios existentes
    r = confirmar_todo(api, v, actualizar_precios=False)
    assert r.json() == {"creados": 0, "actualizados": 0, "sin_cambios": 1, "desactivados": 0}
    assert {p["nombre"]: p["precio"] for p in api.get("/admin/productos").json()["productos"]}["A"] == 10

    # Con actualizar + desactivar faltantes: C se oculta (NO se borra)
    r = confirmar_todo(api, v, actualizar_precios=True, desactivar_faltantes=True)
    assert r.json()["actualizados"] == 1 and r.json()["desactivados"] == 1
    ocultos = api.get("/admin/productos", params={"disponible": "false"}).json()["productos"]
    assert [p["nombre"] for p in ocultos] == ["C"]


def test_parecidos_se_marcan_para_revisar(api):
    crear(api, "Trident morado", 3)
    v = previsualizar(api, xlsx([("Trident morados", 3), ("Trident verde", 3)])).json()
    por = {f["nombre"]: f for f in v["filas"]}
    assert por["Trident morados"]["accion"] == "revisar" and por["Trident morados"]["incluir"] is False
    assert por["Trident morados"]["similar_a"] == "Trident morado"
    assert por["Trident verde"]["accion"] == "crear"
    confirmar_todo(api, v)
    assert "Trident morados" not in [p["nombre"] for p in api.get("/admin/productos").json()["productos"]]


@pytest.mark.skipif(
    not os.path.exists(os.environ.get("EXCEL_PRODUCTOS", "/nonexistent")),
    reason="Define EXCEL_PRODUCTOS con la ruta de tu Excel real para esta prueba",
)
def test_importar_el_excel_real(api):
    ruta = os.environ["EXCEL_PRODUCTOS"]
    contenido = Path(ruta).read_bytes()
    v = previsualizar(api, contenido, Path(ruta).name).json()
    assert v["resumen"]["errores"] == 0
    c = confirmar_todo(api, v)
    assert c.status_code == 200
    n_unicos = v["resumen"]["nuevos"]
    assert c.json()["creados"] == n_unicos > 100
    # segunda vez: idempotente
    v2 = previsualizar(api, contenido, Path(ruta).name).json()
    assert v2["resumen"]["nuevos"] == 0 and v2["resumen"]["cambian_precio"] == 0
    assert len(api.get("/menu").json()["menu"]) == n_unicos


# ---------------------------------------------------------------------------
# HISTORIAL
# ---------------------------------------------------------------------------
@pytest.fixture()
def ventas(api):
    cafe = crear(api, "Café", 30, "Bebida")["id_producto"]
    torta = crear(api, "Torta de jamón", 45)["id_producto"]
    ids = []
    for nombre, mat, items, pago in (
        ("Ana", "1001", [{"id_producto": cafe, "cantidad": 2}], "Efectivo"),
        ("Luis", "1002", [{"id_producto": torta}, {"id_producto": cafe}], "Tarjeta"),
        ("Ana", "1001", [{"id_producto": torta, "cantidad": 3}], "Efectivo"),
    ):
        r = ordenar(api, items, nombre_estudiante=nombre, matricula=mat, metodo_pago=pago)
        assert r.status_code == 200, r.text
        ids.append(r.json()["numero_orden"])
    for i in ids[:2]:  # los dos primeros se entregan
        for estado in ("Preparando", "Listo", "Entregado"):
            assert api.put(f"/pedido/{i}/estado", json={"nuevo_estado": estado}).status_code == 200
    return ids


def test_historial_filtros_y_resumen(api, ventas):
    h = api.get("/admin/historial").json()
    assert h["total_pedidos"] == 3 and float(h["ventas"]) == 60 + 75 + 135

    e = api.get("/admin/historial", params={"estado": "Entregado"}).json()
    assert e["total_pedidos"] == 2 and float(e["ventas"]) == 135 and float(e["ticket_promedio"]) == 67.5
    assert {p["id_pedido"] for p in e["pedidos"]} == set(ventas[:2])

    assert api.get("/admin/historial", params={"matricula": "1002"}).json()["total_pedidos"] == 1
    assert api.get("/admin/historial", params={"matricula": "100"}).json()["total_pedidos"] == 3
    assert api.get("/admin/historial", params={"metodo_pago": "Tarjeta"}).json()["total_pedidos"] == 1
    assert api.get("/admin/historial", params={"id_pedido": ventas[2]}).json()["total_pedidos"] == 1
    # por producto (sin acentos ni mayúsculas) y sin interpretar % _ como comodines
    assert api.get("/admin/historial", params={"producto": "TORTA DE JAMON"}).json()["total_pedidos"] == 2
    assert api.get("/admin/historial", params={"producto": "%"}).json()["total_pedidos"] == 0
    assert api.get("/admin/historial", params={"producto": "cafe", "estado": "Entregado"}).json()["total_pedidos"] == 2

    hoy = main.date.today().isoformat()
    assert api.get("/admin/historial", params={"desde": hoy, "hasta": hoy}).json()["total_pedidos"] == 3
    assert api.get("/admin/historial", params={"hasta": "2020-01-01"}).json()["total_pedidos"] == 0
    assert api.get("/admin/historial", params={"desde": "2099-01-01"}).json()["total_pedidos"] == 0
    assert api.get("/admin/historial", params={"estado": "Inventado"}).status_code == 422


def test_historial_paginacion(api, ventas):
    p1 = api.get("/admin/historial", params={"limite": 2, "offset": 0}).json()
    p2 = api.get("/admin/historial", params={"limite": 2, "offset": 2}).json()
    assert p1["total_pedidos"] == 3 and len(p1["pedidos"]) == 2 and len(p2["pedidos"]) == 1
    ids = [p["id_pedido"] for p in p1["pedidos"] + p2["pedidos"]]
    assert ids == sorted(ids, reverse=True)  # más recientes primero


def test_ranking_y_csv(api, ventas):
    r = api.get("/admin/historial/productos").json()["productos"]
    assert [(x["nombre"], int(x["unidades"]), float(x["importe"])) for x in r] == [
        ("Torta de jamón", 4, 180.0),
        ("Café", 3, 90.0),
    ]
    resp = api.get("/admin/historial/exportar.csv", params={"estado": "Entregado"})
    assert resp.status_code == 200 and resp.headers["content-type"].startswith("text/csv")
    texto = resp.content.decode("utf-8-sig")
    lineas = texto.strip().splitlines()
    assert lineas[0].startswith("Pedido,Fecha,Estudiante") and len(lineas) == 3
    assert "2x Café" in texto and "1x Torta de jamón; 1x Café" in texto


def test_csv_no_permite_inyeccion_de_formulas(api):
    p = crear(api, "Pan", 5)["id_producto"]
    ordenar(api, [{"id_producto": p}], nombre_estudiante="=HYPERLINK(\"http://x\")", matricula="+1")
    texto = api.get("/admin/historial/exportar.csv").content.decode("utf-8-sig")
    assert "'=HYPERLINK" in texto and "'+1" in texto


# ---------------------------------------------------------------------------
# El flujo en tiempo real de la entrega anterior, ahora contra SQL real
# ---------------------------------------------------------------------------
def test_flujo_en_tiempo_real_contra_mysql(api):
    p = crear(api, "Torta", 45)["id_producto"]
    n = ordenar(api, [{"id_producto": p, "cantidad": 2}]).json()["numero_orden"]
    with api.websocket_connect(f"/ws/pedido/{n}") as ws, api.websocket_connect(f"/ws/cocina?token={main.ADMIN_TOKEN}") as cocina:
        assert ws.receive_json()["pedido"]["estado"] == "En Cola"
        activos = api.get("/pedidos_activos").json()["pedidos"]
        assert activos[0]["items"][0] == {"cantidad": 2, "notas": "", "nombre": "Torta"}
        assert api.put(f"/pedido/{n}/estado", json={"nuevo_estado": "Listo"}).status_code == 409  # no se puede saltar
        for estado in ("Preparando", "Listo", "Entregado"):
            assert api.put(f"/pedido/{n}/estado", json={"nuevo_estado": estado}).status_code == 200
            assert ws.receive_json()["pedido"]["estado"] == estado
            assert cocina.receive_json() == {"tipo": "actualizar"}
    assert api.get("/pedidos_activos").json()["pedidos"] == []
