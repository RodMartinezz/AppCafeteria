// Vista HISTORIAL: pedidos pasados con filtros, resumen de ventas, ranking y exportación CSV.
import { api, descargar, esc, dinero, fechaHora, toast, ETIQUETA_ESTADO, COLOR_ESTADO } from './api.js';

const $ = (id) => document.getElementById(id);
const POR_PAGINA = 25;

let offset = 0;
let total = 0;
let solicitud = 0; // descarta respuestas viejas si el usuario busca varias veces seguidas
let iniciado = false;

const isoLocal = (d) => {
  const z = new Date(d.getTime() - d.getTimezoneOffset() * 60000);
  return z.toISOString().slice(0, 10);
};

function valoresFiltros() {
  const filtros = {};
  for (const [k, v] of new FormData($('hist-filtros')).entries()) {
    if (String(v).trim() !== '') filtros[k] = String(v).trim();
  }
  return filtros;
}

function valoresPorDefecto() {
  const f = $('hist-filtros');
  const hoy = new Date();
  const hace7 = new Date(hoy.getTime() - 6 * 86400000);
  f.reset();
  f.desde.value = isoLocal(hace7);
  f.hasta.value = isoLocal(hoy);
  f.estado.value = 'Entregado';
}

function tarjeta(titulo, valor, nota = '') {
  return `<div class="col-12 col-md-4"><div class="card h-100"><div class="card-body py-2">
    <div class="text-muted small">${titulo}</div><div class="fs-3 fw-bold">${valor}</div>
    <div class="text-muted small">${nota}</div></div></div></div>`;
}

function filaPedido(p) {
  const items = p.items
    .map(
      (i) =>
        `<li>${i.cantidad}× ${esc(i.nombre)} <span class="text-muted">(${dinero(i.precio_unitario)} c/u)</span>${i.notas ? ` <i class="text-info">${esc(i.notas)}</i>` : ''}</li>`,
    )
    .join('');
  return `<tr>
    <td>#${p.id_pedido}</td>
    <td class="text-nowrap">${fechaHora(p.fecha_hora)}</td>
    <td>${esc(p.nombre_estudiante)}</td>
    <td>${esc(p.matricula)}</td>
    <td><span class="badge text-bg-${COLOR_ESTADO[p.estado] ?? 'secondary'}">${ETIQUETA_ESTADO[p.estado] ?? esc(p.estado)}</span></td>
    <td>${esc(p.metodo_pago ?? '')}</td>
    <td class="text-end">${dinero(p.total)}</td>
    <td><details><summary class="small">${p.items.length} producto${p.items.length === 1 ? '' : 's'}</summary><ul class="small mb-0 ps-3">${items}</ul></details></td>
  </tr>`;
}

export async function buscar(reiniciarPagina = true) {
  if (reiniciarPagina) offset = 0;
  const mia = ++solicitud;
  const filtros = valoresFiltros();
  try {
    const [h, r] = await Promise.all([
      api('/admin/historial', { params: { ...filtros, limite: POR_PAGINA, offset } }),
      api('/admin/historial/productos', { params: filtros }),
    ]);
    if (mia !== solicitud) return;
    total = h.total_pedidos;

    $('hist-tarjetas').innerHTML =
      tarjeta('Pedidos', total) +
      tarjeta('Ventas', dinero(h.ventas), 'suma de los pedidos filtrados') +
      tarjeta('Ticket promedio', dinero(h.ticket_promedio));

    $('hist-cuerpo').innerHTML =
      h.pedidos.map(filaPedido).join('') ||
      '<tr><td colspan="8" class="text-center text-muted py-4">No hay pedidos con estos filtros</td></tr>';

    const desde = total ? offset + 1 : 0;
    const hasta = Math.min(offset + POR_PAGINA, total);
    $('hist-paginacion-info').textContent = `Mostrando ${desde}–${hasta} de ${total}`;
    $('hist-prev').disabled = offset === 0;
    $('hist-next').disabled = offset + POR_PAGINA >= total;

    $('hist-ranking').innerHTML =
      r.productos
        .map((p) => `<tr><td>${esc(p.nombre)}</td><td class="text-end">${p.unidades}</td><td class="text-end">${dinero(p.importe)}</td></tr>`)
        .join('') || '<tr><td colspan="3" class="text-center text-muted">Sin datos</td></tr>';
  } catch (e) {
    if (e.status !== 401) toast(e.message, 'error');
  }
}

$('hist-filtros').addEventListener('submit', (e) => {
  e.preventDefault();
  buscar();
});
$('hist-limpiar').addEventListener('click', () => {
  $('hist-filtros').reset(); // sin filtros: todo el historial
  buscar();
});
$('hist-prev').addEventListener('click', () => {
  offset = Math.max(0, offset - POR_PAGINA);
  buscar(false);
});
$('hist-next').addEventListener('click', () => {
  offset += POR_PAGINA;
  buscar(false);
});
$('hist-csv').addEventListener('click', async () => {
  try {
    await descargar('/admin/historial/exportar.csv', valoresFiltros(), 'historial_pedidos.csv');
  } catch (e) {
    if (e.status !== 401) toast(e.message, 'error');
  }
});

export function alAbrir() {
  if (!iniciado) {
    iniciado = true;
    valoresPorDefecto(); // últimos 7 días, solo entregados
  }
  buscar();
}
