// Vista COCINA (KDS): pedidos activos en tiempo real.
// El servidor avisa por WebSocket (/ws/cocina); si se cae, consulta cada 5 s.
import { api, WS_URL, getToken, esc, toast } from './api.js';

const $ = (id) => document.getElementById(id);

let activo = false;
let ws = null;
let reintento = 0;
let timerReconexion = null;
let timerPolling = null;

function pintarIndicador(enVivo) {
  const el = $('indicador');
  el.className = 'badge ' + (enVivo ? 'bg-success' : 'bg-warning text-dark');
  el.textContent = enVivo ? '🟢 En vivo' : '🟠 Reconectando… (actualizando cada 5 s)';
}

function tarjeta(p) {
  const items = p.items
    .map((i) => {
      const nota = i.notas ? `<small class="text-info d-block">Nota: ${esc(i.notas)}</small>` : '';
      return `<li><b>${i.cantidad}x</b> ${esc(i.nombre)} ${nota}</li>`;
    })
    .join('');

  let clase = 'estado-encola';
  let boton = `<button class="btn btn-warning w-100 fw-bold mt-3" data-id="${p.id_pedido}" data-estado="Preparando">🔥 Empezar a Preparar</button>`;
  if (p.estado === 'Preparando') {
    clase = 'estado-preparando';
    boton = `<button class="btn btn-success w-100 fw-bold mt-3" data-id="${p.id_pedido}" data-estado="Listo">✅ Marcar como Listo</button>`;
  } else if (p.estado === 'Listo') {
    clase = 'estado-listo';
    boton = `<button class="btn btn-secondary w-100 fw-bold mt-3" data-id="${p.id_pedido}" data-estado="Entregado">📦 Entregar al Alumno</button>`;
  }
  const hora = new Date(p.fecha_hora).toLocaleTimeString();

  return `
    <div class="col-12 col-md-6 col-lg-4">
      <div class="card card-pedido ${clase} shadow">
        <div class="card-body">
          <div class="d-flex justify-content-between align-items-center mb-2">
            <h5 class="card-title text-warning m-0">#${p.id_pedido} - ${esc(p.nombre_estudiante)}</h5>
            <span class="badge text-bg-light">${hora}</span>
          </div>
          <h6 class="text-muted">Matrícula: ${esc(p.matricula)}</h6>
          <hr class="border-secondary">
          <ul class="fs-5 ps-3">${items}</ul>
          ${boton}
        </div>
      </div>
    </div>`;
}

export async function cargarPedidos() {
  try {
    const { pedidos } = await api('/pedidos_activos');
    const contenedor = $('contenedor-pedidos');
    const pendientes = pedidos.filter((p) => p.estado === 'En Cola').length;
    $('contador-cocina').textContent = pendientes;
    $('contador-cocina').hidden = pendientes === 0;
    contenedor.innerHTML = pedidos.length
      ? pedidos.map(tarjeta).join('')
      : "<h4 class='text-center text-muted col-12 mt-5'>No hay pedidos pendientes 😴</h4>";
  } catch (e) {
    if (e.status !== 401) console.error('Error cargando pedidos:', e.message);
  }
}

async function cambiarEstado(boton) {
  boton.disabled = true; // evita doble clic
  try {
    await api(`/pedido/${boton.dataset.id}/estado`, {
      method: 'PUT',
      json: { nuevo_estado: boton.dataset.estado },
    });
  } catch (e) {
    toast('No se pudo actualizar: ' + e.message, 'error');
  }
  cargarPedidos();
}

function conectarWS() {
  if (!activo) return;
  const socket = new WebSocket(`${WS_URL}/ws/cocina?token=${encodeURIComponent(getToken())}`);
  ws = socket;
  socket.onopen = () => {
    reintento = 0;
    pintarIndicador(true);
    cargarPedidos();
  };
  socket.onmessage = (e) => {
    const msg = JSON.parse(e.data);
    if (msg.tipo === 'actualizar') cargarPedidos();
  };
  socket.onclose = (e) => {
    if (!activo || ws !== socket) return;
    pintarIndicador(false);
    if (e.code === 4401) {
      document.dispatchEvent(new CustomEvent('auth-requerida')); // clave inválida: no reintentar
      return;
    }
    reintento = Math.min(reintento + 1, 5);
    timerReconexion = setTimeout(conectarWS, reintento * 1000);
  };
  socket.onerror = () => socket.close();
}

// Un solo manejador para todos los botones de las tarjetas
$('contenedor-pedidos').addEventListener('click', (e) => {
  const boton = e.target.closest('button[data-estado]');
  if (boton) cambiarEstado(boton);
});

export function iniciar() {
  if (activo) return;
  activo = true;
  cargarPedidos();
  conectarWS();
  // Respaldo: si el WebSocket está caído, consulta cada 5 segundos
  timerPolling = setInterval(() => {
    if (!ws || ws.readyState !== WebSocket.OPEN) cargarPedidos();
  }, 5000);
}

export function detener() {
  activo = false;
  clearTimeout(timerReconexion);
  clearInterval(timerPolling);
  if (ws) {
    ws.onclose = null;
    ws.close();
  }
  ws = null;
}

export const alAbrir = () => cargarPedidos();
