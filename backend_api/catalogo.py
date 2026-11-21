"""
Lógica PURA del catálogo (sin base de datos): normalización de nombres, lectura de
Excel/CSV y análisis de la importación. Al no tocar MySQL se prueba fácilmente.
"""
import csv
import io
import re
import unicodedata
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Tuple

MAX_BYTES = 2 * 1024 * 1024
MAX_FILAS = 2000
PRECIO_MAX = Decimal("9999.99")
UMBRAL_SIMILAR = 0.88  # nombres "casi iguales" (typos): se marcan para revisión

CATEGORIAS = ("Comida", "Bebida")
PREPARACIONES = ("Parrilla", "Mostrador")


class ErrorArchivo(ValueError):
    """Archivo ilegible o con formato no soportado (se muestra tal cual al admin)."""


# ---------------------------------------------------------------------------
# NORMALIZACIÓN
# ---------------------------------------------------------------------------
def limpiar_nombre(texto: Any) -> str:
    """'  Chetos   ' -> 'Chetos' (recorta y colapsa espacios; conserva mayúsculas/acentos)."""
    if texto is None:
        return ""
    return re.sub(r"\s+", " ", str(texto)).strip()


def normalizar_nombre(texto: Any) -> str:
    """Clave para detectar duplicados: 'Café  Americano ' == 'cafe americano'."""
    limpio = limpiar_nombre(texto)
    sin_acentos = "".join(
        c for c in unicodedata.normalize("NFKD", limpio) if not unicodedata.combining(c)
    )
    return sin_acentos.casefold()


def parse_precio(valor: Any) -> Tuple[Optional[Decimal], Optional[str]]:
    """Devuelve (precio, None) o (None, motivo_del_error)."""
    if valor is None or (isinstance(valor, str) and not valor.strip()):
        return None, "Falta el precio"
    if isinstance(valor, bool):
        return None, "Precio inválido"
    try:
        if isinstance(valor, (int, float, Decimal)):
            d = Decimal(str(valor))
        else:
            t = str(valor).strip().replace("$", "").replace(" ", "")
            if "," in t and "." in t:
                t = t.replace(",", "")  # 1,250.50
            elif "," in t:
                t = t.replace(",", ".")  # 25,5
            d = Decimal(t)
    except (InvalidOperation, ValueError):
        return None, f"Precio no numérico: {valor!r}"
    if not d.is_finite():
        return None, "Precio inválido"
    d = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if d <= 0:
        return None, "El precio debe ser mayor a 0"
    if d > PRECIO_MAX:
        return None, f"El precio excede el máximo permitido (${PRECIO_MAX})"
    return d, None


# ---------------------------------------------------------------------------
# CATEGORÍA (el Excel no la trae: se sugiere y el admin la revisa en la vista previa)
# ---------------------------------------------------------------------------
_PATRON_BEBIDA = re.compile(
    r"\b(agua|cafe|capuccino|cappuccino|latte|mokaccino|moka|jugo|leche|jaztea|fuze|coca|"
    r"electrolit|calpico|abuelita|chocomilk|nesquik|beber|refresco|bebida|te caliente|te frio)\b"
)


_NO_ES_BEBIDA = ("arroz con leche",)  # contiene 'leche' pero es postre


def inferir_categoria(nombre: str) -> str:
    n = normalizar_nombre(nombre)
    if any(x in n for x in _NO_ES_BEBIDA):
        return "Comida"
    return "Bebida" if _PATRON_BEBIDA.search(n) else "Comida"


def _categoria_de_archivo(valor: Any) -> Optional[str]:
    t = normalizar_nombre(valor)
    if t in ("comida", "comidas", "alimento", "alimentos"):
        return "Comida"
    if t in ("bebida", "bebidas"):
        return "Bebida"
    return None


def _prep_de_archivo(valor: Any) -> Optional[str]:
    t = normalizar_nombre(valor)
    if t == "parrilla":
        return "Parrilla"
    if t == "mostrador":
        return "Mostrador"
    return None


# ---------------------------------------------------------------------------
# LECTURA DE ARCHIVOS  ->  lista de filas crudas
# ---------------------------------------------------------------------------
_ALIAS = {
    "nombre": {"producto", "productos", "nombre", "descripcion", "articulo", "articulos"},
    "precio": {"precio", "precios", "costo", "importe", "precio venta", "precio de venta"},
    "categoria": {"categoria", "categorias", "tipo"},
    "tipo_preparacion": {"tipo preparacion", "tipo_preparacion", "preparacion"},
}


def _detectar_columnas(encabezado: List[Any]) -> Dict[str, int]:
    cols: Dict[str, int] = {}
    for i, celda in enumerate(encabezado):
        t = normalizar_nombre(celda).replace("_", " ")
        for campo, alias in _ALIAS.items():
            if campo not in cols and t in alias:
                cols[campo] = i
    return cols


def _filas_xlsx(contenido: bytes) -> Tuple[str, List[List[Any]]]:
    import openpyxl  # import tardío: solo se necesita al importar

    if contenido[:2] != b"PK":
        raise ErrorArchivo(
            "No es un .xlsx válido. Si es un .xls antiguo, ábrelo en Excel y guárdalo como .xlsx o .csv."
        )
    try:
        wb = openpyxl.load_workbook(io.BytesIO(contenido), read_only=True, data_only=True)
    except Exception as e:  # zip corrupto, etc.
        raise ErrorArchivo(f"No se pudo leer el Excel: {e}")
    for ws in wb.worksheets:
        filas = [list(f) for f in ws.iter_rows(values_only=True)]
        if any(any(c is not None and str(c).strip() for c in f) for f in filas):
            return ws.title, filas
    raise ErrorArchivo("El Excel no tiene datos.")


def _filas_csv(contenido: bytes) -> Tuple[str, List[List[Any]]]:
    try:
        texto = contenido.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = contenido.decode("cp1252")  # CSV guardado por Excel en Windows
    primera = texto.splitlines()[0] if texto.strip() else ""
    delimitador = max(",;\t", key=primera.count) if primera else ","
    return "csv", [list(f) for f in csv.reader(io.StringIO(texto), delimiter=delimitador)]


def leer_archivo(nombre_archivo: str, contenido: bytes) -> Dict[str, Any]:
    """Convierte .xlsx/.csv en filas crudas [{linea, nombre, precio, categoria, tipo_preparacion}]."""
    if not contenido:
        raise ErrorArchivo("El archivo está vacío.")
    if len(contenido) > MAX_BYTES:
        raise ErrorArchivo(f"El archivo excede {MAX_BYTES // (1024 * 1024)} MB.")

    ext = (nombre_archivo or "").rsplit(".", 1)[-1].lower()
    if ext == "xlsx" or ext == "xlsm":
        hoja, filas = _filas_xlsx(contenido)
    elif ext in ("csv", "txt"):
        hoja, filas = _filas_csv(contenido)
    else:
        raise ErrorArchivo("Formato no soportado: usa .xlsx o .csv")

    advertencias: List[str] = []
    cols: Dict[str, int] = {}
    inicio = 0
    for i, fila in enumerate(filas[:10]):  # el encabezado debe estar en las primeras filas
        c = _detectar_columnas(fila)
        if "nombre" in c and "precio" in c:
            cols, inicio = c, i + 1
            break
    if not cols:
        cols = {"nombre": 0, "precio": 1}
        advertencias.append(
            "No se encontraron encabezados 'Producto/Precio': se asumió columna A = nombre y B = precio."
        )

    filas_crudas = []
    for idx in range(inicio, len(filas)):
        fila = filas[idx]

        def celda(campo: str) -> Any:
            j = cols.get(campo)
            return fila[j] if j is not None and j < len(fila) else None

        if all(c is None or not str(c).strip() for c in fila):
            continue  # fila en blanco
        filas_crudas.append(
            {
                "linea": idx + 1,  # número de fila tal como se ve en Excel
                "nombre": celda("nombre"),
                "precio": celda("precio"),
                "categoria": celda("categoria"),
                "tipo_preparacion": celda("tipo_preparacion"),
            }
        )
    if len(filas_crudas) > MAX_FILAS:
        raise ErrorArchivo(f"Demasiadas filas ({len(filas_crudas)}). El máximo es {MAX_FILAS}.")
    if not filas_crudas:
        raise ErrorArchivo("No se encontraron filas de productos.")

    columnas = {
        k: (str(filas[inicio - 1][v]) if inicio else f"columna {chr(65 + v)}") for k, v in cols.items()
    }
    return {"hoja": hoja, "columnas": columnas, "filas": filas_crudas, "advertencias": advertencias}


# ---------------------------------------------------------------------------
# ANÁLISIS: qué pasaría con cada fila si se importa
# ---------------------------------------------------------------------------
def _numeros(clave: str) -> List[str]:
    return re.findall(r"\d+", clave)


def _parecido(a: str, b: str) -> float:
    """0..1. Si ambos traen cifras distintas ('1Lt' vs '1.5Lt', '500ml' vs '1Lt') son
    presentaciones diferentes de un producto, no un typo: no se consideran parecidos."""
    na, nb = _numeros(a), _numeros(b)
    if na and nb and na != nb:
        return 0.0
    return SequenceMatcher(None, a, b).ratio()


def _mas_parecido(clave: str, candidatas: Dict[str, str]) -> Optional[str]:
    """Nombre (original) más parecido a `clave` si supera el umbral; None si no hay."""
    mejor, mejor_valor = None, UMBRAL_SIMILAR
    for otra_clave, original in candidatas.items():
        if otra_clave == clave:
            continue
        v = _parecido(clave, otra_clave)
        if v >= mejor_valor:
            mejor, mejor_valor = original, v
    return mejor


def analizar_filas(crudas: List[Dict[str, Any]], catalogo: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    crudas   : salida de leer_archivo()['filas']
    catalogo : productos actuales [{id_producto, nombre, nombre_norm, precio, disponible}]

    Cada fila resultante trae una `accion`:
      crear · actualizar_precio · sin_cambios · duplicado_ignorado · revisar · error
    """
    en_bd = {p["nombre_norm"]: p for p in catalogo}
    nombres_bd = {p["nombre_norm"]: p["nombre"] for p in catalogo}

    vistos: Dict[str, Dict[str, Any]] = {}  # clave -> fila aceptada del archivo
    nombres_archivo: Dict[str, str] = {}  # para comparar parecidos dentro del archivo
    salida: List[Dict[str, Any]] = []

    for r in crudas:
        nombre = limpiar_nombre(r["nombre"])
        fila: Dict[str, Any] = {
            "linea": r["linea"],
            "nombre": nombre,
            "precio": None,
            "categoria": None,
            "tipo_preparacion": None,
            "categoria_inferida": False,
            "accion": "error",
            "incluir": False,
            "mensaje": "",
            "precio_actual": None,
            "similar_a": None,
        }
        salida.append(fila)

        if not nombre:
            fila["mensaje"] = "Falta el nombre"
            continue
        if len(nombre) > 100:
            fila["mensaje"] = "El nombre excede 100 caracteres"
            continue
        precio, motivo = parse_precio(r["precio"])
        if motivo:
            fila["mensaje"] = motivo
            continue
        fila["precio"] = float(precio)

        cat = _categoria_de_archivo(r["categoria"])
        fila["categoria"] = cat or inferir_categoria(nombre)
        fila["categoria_inferida"] = cat is None
        fila["tipo_preparacion"] = _prep_de_archivo(r["tipo_preparacion"]) or "Mostrador"

        clave = normalizar_nombre(nombre)

        # 1) Repetido dentro del mismo archivo
        if clave in vistos:
            previo = vistos[clave]
            if Decimal(str(previo["precio"])) == precio:
                fila.update(
                    accion="duplicado_ignorado",
                    mensaje=f"Repetido (igual a la fila {previo['linea']}): se ignora",
                )
            else:
                fila["mensaje"] = (
                    f"Aparece también en la fila {previo['linea']} con otro precio "
                    f"(${previo['precio']:.2f} vs ${float(precio):.2f}). Corrige el archivo."
                )
            continue
        vistos[clave] = fila

        # 2) Ya existe en la base de datos
        existente = en_bd.get(clave)
        if existente:
            actual = Decimal(str(existente["precio"])).quantize(Decimal("0.01"))
            fila["precio_actual"] = float(actual)
            if actual == precio:
                fila.update(accion="sin_cambios", mensaje="Ya existe con el mismo precio")
            else:
                fila.update(
                    accion="actualizar_precio",
                    incluir=True,
                    mensaje=f"Cambia de ${float(actual):.2f} a ${float(precio):.2f}",
                )
            nombres_archivo[clave] = nombre
            continue

        # 3) Producto nuevo (¿o un typo de uno existente?)
        parecido = _mas_parecido(clave, {**nombres_bd, **nombres_archivo})
        nombres_archivo[clave] = nombre
        if parecido:
            fila.update(
                accion="revisar",
                similar_a=parecido,
                mensaje=f"Se parece a «{parecido}». ¿Es el mismo producto? Márcalo solo si es distinto.",
            )
        else:
            fila.update(accion="crear", incluir=True, mensaje="Producto nuevo")

    resumen = {
        "filas_leidas": len(salida),
        "nuevos": sum(f["accion"] == "crear" for f in salida),
        "cambian_precio": sum(f["accion"] == "actualizar_precio" for f in salida),
        "sin_cambios": sum(f["accion"] == "sin_cambios" for f in salida),
        "duplicados_ignorados": sum(f["accion"] == "duplicado_ignorado" for f in salida),
        "para_revisar": sum(f["accion"] == "revisar" for f in salida),
        "errores": sum(f["accion"] == "error" for f in salida),
    }
    claves_archivo = sorted(vistos.keys())
    faltantes = [
        p["nombre"] for p in catalogo if p.get("disponible") and p["nombre_norm"] not in vistos
    ]
    resumen["faltantes_en_archivo"] = len(faltantes)
    return {
        "resumen": resumen,
        "filas": salida,
        "claves_archivo": claves_archivo,
        "faltantes_en_archivo": faltantes[:50],
    }
