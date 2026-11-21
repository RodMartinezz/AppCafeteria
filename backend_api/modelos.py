"""Modelos Pydantic del panel de administración (catálogo, importación, historial)."""
from decimal import Decimal
from typing import Annotated, List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

from catalogo import limpiar_nombre

Categoria = Literal["Comida", "Bebida"]
Preparacion = Literal["Parrilla", "Mostrador"]
Precio = Annotated[Decimal, Field(gt=0, le=Decimal("9999.99"), decimal_places=2)]


def _nombre_valido(v: str) -> str:
    limpio = limpiar_nombre(v)
    if not limpio:
        raise ValueError("El nombre no puede estar vacío")
    return limpio


class ProductoNuevo(BaseModel):
    nombre: str = Field(max_length=100)
    precio: Precio
    categoria: Categoria
    tipo_preparacion: Preparacion = "Mostrador"
    disponible: bool = True

    _limpiar = field_validator("nombre")(_nombre_valido)


class ProductoEditar(BaseModel):
    """Edición parcial: solo se cambia lo que venga en la petición."""

    nombre: Optional[str] = Field(default=None, max_length=100)
    precio: Optional[Precio] = None
    categoria: Optional[Categoria] = None
    tipo_preparacion: Optional[Preparacion] = None
    disponible: Optional[bool] = None

    @field_validator("nombre")
    @classmethod
    def _nombre(cls, v: Optional[str]) -> Optional[str]:
        return None if v is None else _nombre_valido(v)

    @model_validator(mode="after")
    def _algo_que_cambiar(self):
        if not self.model_fields_set:
            raise ValueError("No se indicó ningún campo para modificar")
        return self


class FilaImportacion(BaseModel):
    nombre: str = Field(max_length=100)
    precio: Precio
    categoria: Categoria
    tipo_preparacion: Preparacion = "Mostrador"

    _limpiar = field_validator("nombre")(_nombre_valido)


class ConfirmarImportacion(BaseModel):
    filas: List[FilaImportacion] = Field(default_factory=list, max_length=2000)
    actualizar_precios: bool = True
    # Opcional y peligroso: oculta del menú lo que NO venga en el archivo
    desactivar_faltantes: bool = False
    claves_archivo: List[str] = Field(default_factory=list, max_length=2000)

    @model_validator(mode="after")
    def _coherente(self):
        if not self.filas and not self.desactivar_faltantes:
            raise ValueError("No hay filas para importar")
        if self.desactivar_faltantes and not self.claves_archivo:
            raise ValueError("Para desactivar faltantes se requiere la lista de productos del archivo")
        return self
