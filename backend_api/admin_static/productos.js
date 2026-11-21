// Vista PRODUCTOS: catálogo editable en línea, alta de productos e importación Excel/CSV.
import { api, esc, normalizar, toast, mostrarError, dinero, fechaHora } from './api.js';

const $ = (id) => document.getElementById(id);

let productos = [];

// ===========================================================================
// TABLA DEL CATÁLOGO
// ===========================================================================
export async function cargar() {
  try {
    productos = (await api('/admin/productos')).productos;
    pintar();
  } catch (e) {
    if (e.status !== 401) toast(e.message, 'error');
  }
}

function filtrados() {
  const q = normalizar($('prod-buscar').value);
  const cat = $('prod-categoria').value;
  const est = $('prod-estado').value;
  return productos.filter(
    (p) =>
      (!q || normalizar(p.nombre).includes(q)) &&
      (!cat || p.categoria === cat) &&
      (!est || (est === 'si') === p.disponible),
  );
}

const opciones = (lista, actual) =>
  lista.map((o) => `<option${o === actual ? ' selected' : ''}>${o}</option>`).join('');

function filaHtml(p) {
  return `
    <tr data-id="${p.id_producto}" class="${p.disponible ? '' : 'oculto'}">
      <td><input class="form-control form-control-sm celda-nombre" data-campo="nombre" value="${esc(p.nombre)}" maxlength="100" aria-label="Nombre"></td>
      <td><select class="form-select form-select-sm" data-campo="categoria" aria-label="Categoría">${opciones(['Comida', 'Bebida'], p.categoria)}</select></td>
      <td><select class="form-select form-select-sm" data-campo="tipo_preparacion" aria-label="Preparación">${opciones(['Mostrador', 'Parrilla'], p.tipo_preparacion)}</select></td>
      <td><div class="input-group input-group-sm"><span class="input-group-text">$</span><input type="number" step="0.01" min="0.01" max="9999.99" class="form-control" data-campo="precio" value="${Number(p.precio).toFixed(2)}" aria-label="Precio"></div></td>
      <td class="text-center"><div class="form-check form-switch d-inline-block m-0"><input class="form-check-input" type="checkbox" role="switch" data-campo="disponible" ${p.disponible ? 'checked' : ''} aria-label="Disponible"></div></td>
      <td><button class="btn btn-sm btn-outline-secondary" data-precios="${p.id_producto}" title="Historial de precios">🕘</button></td>
    </tr>`;
}

function pintarResumen() {
  const disp = productos.filter((p) => p.disponible).length;
  $('prod-resumen').textContent =
    `${filtrados().length} de ${productos.length} · ${disp} disponibles · ${productos.length - disp} ocultos`;
}

function pintar() {
  const lista = filtrados();
  $('prod-cuerpo').innerHTML =
    lista.map(filaHtml).join('') ||
    '<tr><td colspan="6" class="text-center text-muted py-4">No hay productos con estos filtros</td></tr>';
  pintarResumen();
}

function sincronizarFila(tr, p) {
  tr.classList.toggle('oculto', !p.disponible);
  for (const campo of ['nombre', 'categoria', 'tipo_preparacion']) {
    tr.querySelector(`[data-campo="${campo}"]`).value = p[campo];
  }
  tr.querySelector('[data-campo="precio"]').value = Number(p.precio).toFixed(2);
  tr.querySelector('[data-campo="disponible"]').checked = p.disponible;
}

function mensajeCambio(campo, antes, ahora) {
  if (campo === 'precio') return `Precio de «${ahora.nombre}»: ${dinero(antes.precio)} → ${dinero(ahora.precio)}`;
  if (campo === 'disponible') return `«${ahora.nombre}» ${ahora.disponible ? 'ya está disponible' : 'se ocultó del menú'}`;
  return `«${ahora.nombre}» actualizado`;
}

// Cada cambio en una casilla se guarda de inmediato (un solo manejador para toda la tabla)
$('prod-cuerpo').addEventListener('change', async (e) => {
  const campo = e.target.dataset.campo;
  if (!campo) return;
  const tr = e.target.closest('tr');
  const actual = productos.find((p) => p.id_producto === Number(tr.dataset.id));
  const antes = { ...actual };

  let valor = e.target.type === 'checkbox' ? e.target.checked : e.target.value;
  if (campo === 'precio') {
    valor = Math.round(Number(valor) * 100) / 100;
    if (!(valor > 0)) {
      toast('El precio debe ser mayor a 0', 'error');
      return sincronizarFila(tr, actual);
    }
  }
  if (campo === 'nombre') {
    valor = valor.trim().replace(/\s+/g, ' ');
    if (!valor) {
      toast('El nombre no puede quedar vacío', 'error');
      return sincronizarFila(tr, actual);
    }
  }
  if (valor === actual[campo]) return sincronizarFila(tr, actual); // sin cambios reales

  tr.classList.add('guardando');
  try {
    const nuevo = await api(`/admin/productos/${actual.id_producto}`, { method: 'PUT', json: { [campo]: valor } });
    Object.assign(actual, nuevo);
    sincronizarFila(tr, actual);
    pintarResumen();
    toast(mensajeCambio(campo, antes, nuevo));
  } catch (err) {
    if (err.status !== 401) toast(err.message, 'error');
    sincronizarFila(tr, actual); // vuelve al valor guardado
    tr.classList.add('error');
    setTimeout(() => tr.classList.remove('error'), 1500);
  } finally {
    tr.classList.remove('guardando');
  }
});

for (const id of ['prod-buscar', 'prod-categoria', 'prod-estado']) {
  $(id).addEventListener('input', pintar);
}

// ===========================================================================
// HISTORIAL DE PRECIOS DE UN PRODUCTO
// ===========================================================================
const ORIGEN = { manual: 'Manual', excel: 'Importación', creacion: 'Alta' };

$('prod-cuerpo').addEventListener('click', async (e) => {
  const boton = e.target.closest('[data-precios]');
  if (!boton) return;
  const p = productos.find((x) => x.id_producto === Number(boton.dataset.precios));
  try {
    const { cambios } = await api(`/admin/productos/${p.id_producto}/precios`);
    $('precios-titulo').textContent = `Precios de «${p.nombre}»`;
    $('precios-cuerpo').innerHTML = cambios
      .map(
        (c) =>
          `<tr><td>${fechaHora(c.cambiado_en)}</td><td>${c.precio_anterior == null ? '—' : dinero(c.precio_anterior)}</td><td>${dinero(c.precio_nuevo)}</td><td>${ORIGEN[c.origen] ?? esc(c.origen)}</td></tr>`,
      )
      .join('');
    $('dlg-precios').showModal();
  } catch (err) {
    if (err.status !== 401) toast(err.message, 'error');
  }
});

// ===========================================================================
// NUEVO PRODUCTO
// ===========================================================================
$('prod-btn-nuevo').addEventListener('click', () => {
  $('form-producto').reset();
  mostrarError($('producto-error'), '');
  $('dlg-producto').showModal();
  $('form-producto').nombre.focus();
});

$('form-producto').addEventListener('submit', async (e) => {
  e.preventDefault();
  const f = e.target;
  try {
    const creado = await api('/admin/productos', {
      method: 'POST',
      json: {
        nombre: f.nombre.value,
        precio: Number(f.precio.value),
        categoria: f.categoria.value,
        tipo_preparacion: f.tipo_preparacion.value,
        disponible: f.disponible.checked,
      },
    });
    $('dlg-producto').close();
    toast(`«${creado.nombre}» agregado`);
    cargar();
  } catch (err) {
    if (err.status !== 401) mostrarError($('producto-error'), err.message);
  }
});

// ===========================================================================
// IMPORTACIÓN EXCEL / CSV  (2 pasos: vista previa → confirmar)
// ===========================================================================
let vista = null; // respuesta de /previsualizar; las ediciones del admin se hacen sobre vista.filas

const BADGE = {
  crear: ['success', 'Nuevo'],
  actualizar_precio: ['info', 'Cambia precio'],
  sin_cambios: ['secondary', 'Sin cambios'],
  duplicado_ignorado: ['secondary', 'Repetido'],
  revisar: ['warning', 'Revisar'],
  error: ['danger', 'Error'],
};
const CON_DATOS_EDITABLES = new Set(['crear', 'actualizar_precio', 'revisar']);
const PUEDE_ELEGIR_CATEGORIA = new Set(['crear', 'revisar']); // en existentes se conserva la de la BD
const SE_PUEDE_INCLUIR = CON_DATOS_EDITABLES;

function reiniciarImportacion() {
  vista = null;
  $('imp-archivo').value = '';
  $('imp-paso2').hidden = true;
  $('imp-resultado').hidden = true;
  $('imp-paso1').hidden = false;
  $('imp-confirmar').hidden = true;
  $('imp-cerrar').textContent = 'Cancelar';
  $('imp-actualizar').checked = true;
  $('imp-desactivar').checked = false;
  $('imp-mostrar').value = '';
  mostrarError($('imp-error'), '');
}

$('prod-btn-importar').addEventListener('click', () => {
  reiniciarImportacion();
  $('dlg-importar').showModal();
});

$('imp-analizar').addEventListener('click', async () => {
  const archivo = $('imp-archivo').files[0];
  mostrarError($('imp-error'), '');
  if (!archivo) return mostrarError($('imp-error'), 'Elige primero un archivo .xlsx o .csv');
  const form = new FormData();
  form.append('archivo', archivo);
  $('imp-analizar').disabled = true;
  try {
    vista = await api('/admin/productos/importar/previsualizar', { method: 'POST', form });
    pintarVista();
  } catch (e) {
    vista = null;
    $('imp-paso2').hidden = true;
    $('imp-confirmar').hidden = true;
    if (e.status !== 401) mostrarError($('imp-error'), e.message);
  } finally {
    $('imp-analizar').disabled = false;
  }
});

function pintarVista() {
  const r = vista.resumen;
  $('imp-paso2').hidden = false;
  $('imp-confirmar').hidden = false;
  const cols = Object.entries(vista.columnas).map(([k, v]) => `${k} ← «${esc(v)}»`).join(' · ');
  $('imp-info').innerHTML = `Archivo <b>${esc(vista.archivo)}</b> · hoja «${esc(vista.hoja)}» · columnas: ${cols}`;
  $('imp-advertencias').innerHTML = vista.advertencias
    .map((a) => `<div class="alert alert-warning py-1 small mb-2">${esc(a)}</div>`)
    .join('');
  $('imp-resumen').innerHTML = [
    ['success', r.nuevos, 'nuevos'],
    ['info', r.cambian_precio, 'cambian de precio'],
    ['secondary', r.sin_cambios, 'sin cambios'],
    ['secondary', r.duplicados_ignorados, 'repetidos ignorados'],
    ['warning', r.para_revisar, 'por revisar'],
    ['danger', r.errores, 'con error'],
  ]
    .filter(([, n]) => n > 0)
    .map(([c, n, t]) => `<span class="badge text-bg-${c} fs-6">${n} ${t}</span>`)
    .join('');
  $('imp-faltantes').textContent = r.faltantes_en_archivo
    ? `(hay ${r.faltantes_en_archivo} en el catálogo: ${vista.faltantes_en_archivo.slice(0, 4).join(', ')}…)`
    : '(ninguno)';
  pintarFilas();
}

function celdaPrecio(f, i) {
  if (!CON_DATOS_EDITABLES.has(f.accion)) return f.precio == null ? '—' : dinero(f.precio);
  return `<input type="number" step="0.01" min="0.01" max="9999.99" class="form-control form-control-sm" data-campo="precio" value="${Number(f.precio).toFixed(2)}">`;
}

function celdaSelect(f, campo, lista) {
  if (!PUEDE_ELEGIR_CATEGORIA.has(f.accion)) {
    return f.accion === 'actualizar_precio' ? '<span class="text-muted small">(se conserva)</span>' : '—';
  }
  const sugerida = campo === 'categoria' && f.categoria_inferida ? '<div class="sugerida text-warning">sugerida</div>' : '';
  return `<select class="form-select form-select-sm" data-campo="${campo}">${opciones(lista, f[campo])}</select>${sugerida}`;
}

function pintarFilas() {
  const mostrar = $('imp-mostrar').value;
  $('imp-cuerpo').innerHTML = vista.filas
    .map((f, i) => ({ f, i }))
    .filter(({ f }) => !mostrar || f.accion === mostrar)
    .map(({ f, i }) => {
      const [color, etiqueta] = BADGE[f.accion];
      const clase = { error: 'fila-error', revisar: 'fila-revisar', duplicado_ignorado: 'fila-ignorada', sin_cambios: 'fila-ignorada' }[f.accion] || '';
      return `<tr data-i="${i}" class="${clase}">
        <td><input type="checkbox" class="form-check-input" data-campo="incluir" ${f.incluir ? 'checked' : ''} ${SE_PUEDE_INCLUIR.has(f.accion) ? '' : 'disabled'}></td>
        <td class="text-muted">${f.linea}</td>
        <td>${esc(f.nombre) || '<i class="text-muted">(vacío)</i>'}</td>
        <td>${celdaPrecio(f, i)}</td>
        <td>${celdaSelect(f, 'categoria', ['Comida', 'Bebida'])}</td>
        <td>${celdaSelect(f, 'tipo_preparacion', ['Mostrador', 'Parrilla'])}</td>
        <td><span class="badge text-bg-${color}">${etiqueta}</span> <span class="small text-muted">${esc(f.mensaje)}</span></td>
      </tr>`;
    })
    .join('');
  actualizarBotonConfirmar();
}

function actualizarBotonConfirmar() {
  const n = vista.filas.filter((f) => f.incluir).length;
  const boton = $('imp-confirmar');
  boton.textContent = n ? `Importar ${n} producto${n === 1 ? '' : 's'}` : 'Importar';
  boton.disabled = n === 0 && !$('imp-desactivar').checked;
}

$('imp-mostrar').addEventListener('change', pintarFilas);
$('imp-desactivar').addEventListener('change', actualizarBotonConfirmar);

// Las ediciones del admin se guardan en vista.filas (no se pierden al filtrar la tabla)
$('imp-cuerpo').addEventListener('change', (e) => {
  const campo = e.target.dataset.campo;
  if (!campo) return;
  const f = vista.filas[Number(e.target.closest('tr').dataset.i)];
  if (campo === 'incluir') f.incluir = e.target.checked;
  else if (campo === 'precio') f.precio = Number(e.target.value);
  else f[campo] = e.target.value;
  if (campo === 'categoria') f.categoria_inferida = false;
  actualizarBotonConfirmar();
});

$('imp-confirmar').addEventListener('click', async () => {
  mostrarError($('imp-error'), '');
  const incluidas = vista.filas.filter((f) => f.incluir);
  const mala = incluidas.find((f) => !(Number(f.precio) > 0));
  if (mala) return mostrarError($('imp-error'), `La fila ${mala.linea} («${mala.nombre}») tiene un precio inválido`);

  const desactivar = $('imp-desactivar').checked;
  if (desactivar) {
    const n = vista.resumen.faltantes_en_archivo;
    if (!confirm(`Se ocultarán del menú ${n} producto(s) que NO vienen en el archivo. ¿Continuar?`)) return;
  }

  $('imp-confirmar').disabled = true;
  try {
    const r = await api('/admin/productos/importar/confirmar', {
      method: 'POST',
      json: {
        filas: incluidas.map(({ nombre, precio, categoria, tipo_preparacion }) => ({
          nombre,
          precio: Number(precio),
          categoria,
          tipo_preparacion,
        })),
        actualizar_precios: $('imp-actualizar').checked,
        desactivar_faltantes: desactivar,
        claves_archivo: vista.claves_archivo,
      },
    });
    $('imp-paso1').hidden = true;
    $('imp-paso2').hidden = true;
    $('imp-confirmar').hidden = true;
    $('imp-cerrar').textContent = 'Cerrar';
    $('imp-resultado').hidden = false;
    $('imp-resultado').innerHTML = `
      <div class="alert alert-success mb-0">
        <h6 class="alert-heading">✅ Importación completada</h6>
        ${r.creados} creados · ${r.actualizados} precios actualizados · ${r.sin_cambios} sin cambios · ${r.desactivados} ocultados
      </div>`;
    toast('Importación completada');
    cargar();
  } catch (e) {
    $('imp-confirmar').disabled = false;
    if (e.status !== 401) mostrarError($('imp-error'), e.message);
  }
});
