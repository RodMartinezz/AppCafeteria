// Arranque del panel: inicio de sesión con token y navegación por pestañas.
import { api, getToken, setToken, clearToken, activarCierreDeDialogos, mostrarError } from './api.js';
import * as cocina from './cocina.js';
import * as productos from './productos.js';
import * as historial from './historial.js';

activarCierreDeDialogos();

const $ = (id) => document.getElementById(id);
// Cada vista expone alAbrir(): se llama al entrar a su pestaña para refrescar sus datos
const vistas = {
  cocina,
  productos: { alAbrir: productos.cargar },
  historial,
};

// ---------------------------------------------------------------- pestañas
function mostrar(nombre) {
  if (!vistas[nombre]) nombre = 'cocina';
  for (const seccion of document.querySelectorAll('main > section')) {
    seccion.hidden = seccion.dataset.vista !== nombre;
  }
  for (const boton of document.querySelectorAll('#pestanas button')) {
    const activa = boton.dataset.vista === nombre;
    boton.classList.toggle('active', activa);
    boton.setAttribute('aria-selected', String(activa));
  }
  history.replaceState(null, '', '#' + nombre);
  vistas[nombre].alAbrir?.();
}

$('pestanas').addEventListener('click', (e) => {
  const boton = e.target.closest('button[data-vista]');
  if (boton) mostrar(boton.dataset.vista);
});

// ---------------------------------------------------------------- sesión
const dlgLogin = $('dlg-login');
dlgLogin.addEventListener('cancel', (e) => e.preventDefault()); // sin clave no se puede cerrar

function pedirLogin(mensaje = '') {
  cocina.detener();
  mostrarError($('login-error'), mensaje);
  if (!dlgLogin.open) dlgLogin.showModal();
  $('login-clave').focus();
}

function arrancar() {
  cocina.iniciar();
  mostrar(location.hash.slice(1) || 'cocina');
}

$('form-login').addEventListener('submit', async (e) => {
  e.preventDefault();
  setToken($('login-clave').value);
  try {
    await api('/pedidos_activos'); // comprueba la clave
    $('login-clave').value = '';
    dlgLogin.close();
    arrancar();
  } catch (err) {
    if (err.status !== 401) mostrarError($('login-error'), err.message);
    // si fue 401, el evento 'auth-requerida' ya mostró «clave incorrecta»
  }
});

document.addEventListener('auth-requerida', () => {
  clearToken();
  pedirLogin('Clave incorrecta o sesión vencida');
});

$('btn-salir').addEventListener('click', () => {
  clearToken();
  pedirLogin();
});

if (getToken()) arrancar();
else pedirLogin();
