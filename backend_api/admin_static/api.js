// Utilidades compartidas: acceso a la API con token, formato y avisos.

const CLAVE = 'admin_token';
export const getToken = () => sessionStorage.getItem(CLAVE) || '';
export const setToken = (t) => sessionStorage.setItem(CLAVE, t);
export const clearToken = () => sessionStorage.removeItem(CLAVE);

// Abierto desde http://<IP>:8000/admin usa el mismo servidor (sin IP fija).
export const API_URL = location.protocol.startsWith('http')
  ? location.origin
  : 'http://192.168.100.182:8000';
export const WS_URL = API_URL.replace(/^http/, 'ws');

export class ErrorApi extends Error {
  constructor(status, mensaje) {
    super(mensaje);
    this.status = status;
  }
}

function mensajeDeError(data, status) {
  if (data && typeof data.detail === 'string') return data.detail;
  if (data && Array.isArray(data.detail)) {
    return data.detail.map((d) => `${(d.loc || []).slice(1).join('.')}: ${d.msg}`).join('; ');
  }
  return `Error ${status}`;
}

function construirUrl(path, params) {
  const url = new URL(API_URL + path);
  for (const [k, v] of Object.entries(params || {})) {
    if (v !== undefined && v !== null && v !== '') url.searchParams.set(k, v);
  }
  return url;
}

async function pedir(path, { method = 'GET', json, form, params } = {}) {
  const headers = { 'X-Admin-Token': getToken() };
  let body;
  if (json !== undefined) {
    headers['Content-Type'] = 'application/json';
    body = JSON.stringify(json);
  } else if (form) {
    body = form;
  }
  let res;
  try {
    res = await fetch(construirUrl(path, params), { method, headers, body });
  } catch {
    throw new ErrorApi(0, 'No se pudo conectar con el servidor');
  }
  if (res.status === 401) {
    document.dispatchEvent(new CustomEvent('auth-requerida'));
    throw new ErrorApi(401, 'Clave de administrador incorrecta');
  }
  return res;
}

/** Llama a la API y devuelve el JSON; lanza ErrorApi con un mensaje legible si falla. */
export async function api(path, opciones = {}) {
  const res = await pedir(path, opciones);
  const data = await res.json().catch(() => null);
  if (!res.ok) throw new ErrorApi(res.status, mensajeDeError(data, res.status));
  return data;
}

/** Descarga un archivo (el enlace directo no puede mandar el token en la cabecera). */
export async function descargar(path, params, nombreArchivo) {
  const res = await pedir(path, { params });
  if (!res.ok) throw new ErrorApi(res.status, `No se pudo descargar (${res.status})`);
  const blob = await res.blob();
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = nombreArchivo;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

// ---------------------------------------------------------------- formato
// Los textos que escribe el alumno (nombre, notas) se escapan SIEMPRE antes de usar innerHTML.
export function esc(texto) {
  const d = document.createElement('div');
  d.textContent = texto ?? '';
  return d.innerHTML.replace(/"/g, '&quot;');
}

export const dinero = (n) => '$' + Number(n ?? 0).toFixed(2);

export function fechaHora(s) {
  if (!s) return '';
  return new Date(s).toLocaleString('es-MX', { dateStyle: 'short', timeStyle: 'short' });
}

/** Para buscar sin importar mayúsculas ni acentos ("cafe" encuentra "Café"). */
export const normalizar = (s) =>
  String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

export const ETIQUETA_ESTADO = {
  'En Cola': 'Pendiente',
  Preparando: 'En preparación',
  Listo: 'Listo',
  Entregado: 'Entregado',
};
export const COLOR_ESTADO = {
  'En Cola': 'danger',
  Preparando: 'warning',
  Listo: 'success',
  Entregado: 'secondary',
};

export function toast(mensaje, tipo = 'ok') {
  const caja = document.getElementById('toasts');
  const div = document.createElement('div');
  div.className = `toast-msg toast-${tipo}`;
  div.textContent = mensaje;
  caja.appendChild(div);
  setTimeout(() => div.remove(), tipo === 'error' ? 6000 : 3500);
}

export function mostrarError(elemento, mensaje) {
  elemento.textContent = mensaje;
  elemento.hidden = !mensaje;
}

/** Cierra el <dialog> más cercano cuando se pulsa un botón con data-cerrar. */
export function activarCierreDeDialogos() {
  document.addEventListener('click', (e) => {
    const boton = e.target.closest('[data-cerrar]');
    if (boton) boton.closest('dialog')?.close();
  });
}
