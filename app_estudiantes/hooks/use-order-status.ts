import { useEffect, useState } from 'react';
import { AppState } from 'react-native';

import { API_URL, WS_URL } from '@/constants/api';

export type EstadoPedido = 'En Cola' | 'Preparando' | 'Listo' | 'Entregado';

export interface ItemPedido {
  cantidad: number;
  nombre: string;
  notas?: string | null;
}

export interface Pedido {
  id_pedido: number;
  nombre_estudiante: string;
  matricula: string;
  estado: EstadoPedido;
  total: number;
  metodo_pago: string | null;
  fecha_hora: string;
  items: ItemPedido[];
  /** Pedidos que siguen en cocina y entraron antes (solo cuando está 'En Cola') */
  pedidos_antes: number;
}

const POLLING_MS = 4000; // respaldo cuando no hay WebSocket
const SIN_NOTICIAS_MS = 50000; // el servidor manda latido cada 20 s
const CONEXION_MS = 8000; // tiempo máximo para abrir el WebSocket
const CODIGO_NO_EXISTE = 4404; // el servidor: "ese pedido no existe, no reintentes"

/**
 * Mantiene sincronizado el estado de un pedido.
 *  - Principal: WebSocket  ws://.../ws/pedido/{id}  (el servidor empuja los cambios).
 *  - Respaldo : GET /pedido/{id} cada 4 s mientras el WebSocket no esté abierto.
 *  - Se reconecta solo (backoff 1, 2, 4... hasta 15 s) y al volver la app a primer plano.
 *  - Se detiene cuando el pedido llega a 'Entregado'.
 */
export function useOrderStatus(idPedido: number | null) {
  const [pedido, setPedido] = useState<Pedido | null>(null);
  const [conectado, setConectado] = useState(false);
  const [noExiste, setNoExiste] = useState(false);

  // Si cambia el pedido, se descarta lo anterior (patrón "ajustar estado al cambiar una prop")
  const [idPrevio, setIdPrevio] = useState<number | null>(idPedido);
  if (idPrevio !== idPedido) {
    setIdPrevio(idPedido);
    setPedido(null);
    setConectado(false);
    setNoExiste(false);
  }

  const finalizado = pedido?.estado === 'Entregado' && pedido.id_pedido === idPedido;

  useEffect(() => {
    if (idPedido == null || finalizado) return;

    let activo = true;
    let ws: WebSocket | null = null;
    let reintentos = 0;
    let timerReconexion: ReturnType<typeof setTimeout> | null = null;
    let timerPolling: ReturnType<typeof setInterval> | null = null;
    let watchdog: ReturnType<typeof setTimeout> | null = null;

    const cargarPorHttp = async () => {
      try {
        const res = await fetch(`${API_URL}/pedido/${idPedido}`);
        if (!activo) return;
        if (res.status === 404) return setNoExiste(true);
        if (res.ok) setPedido(await res.json());
      } catch {
        // sin red: se reintenta en el siguiente ciclo
      }
    };

    const iniciarPolling = () => {
      if (timerPolling) return;
      cargarPorHttp();
      timerPolling = setInterval(cargarPorHttp, POLLING_MS);
    };
    const detenerPolling = () => {
      if (timerPolling) clearInterval(timerPolling);
      timerPolling = null;
    };

    const conectar = () => {
      if (!activo) return;
      const socket = new WebSocket(`${WS_URL}/ws/pedido/${idPedido}`);
      ws = socket;
      let cerrado = false;

      // Se ejecuta UNA sola vez por conexión, la dispare 'close', 'error' o el watchdog
      // (según la plataforma llega uno, otro o ambos): programa el reintento.
      const alCerrar = (codigo?: number) => {
        if (cerrado) return;
        cerrado = true;
        if (watchdog) clearTimeout(watchdog);
        if (!activo || ws !== socket) return;
        setConectado(false);
        if (codigo === CODIGO_NO_EXISTE) return setNoExiste(true);
        iniciarPolling(); // mientras tanto, seguimos enterándonos por HTTP
        reintentos += 1;
        const espera = Math.min(1000 * 2 ** (reintentos - 1), 15000);
        timerReconexion = setTimeout(conectar, espera);
      };

      // Si el celular cambia de red o duerme, 'close' puede tardar mucho (o no llegar):
      // sin noticias del servidor en este plazo, forzamos el cierre y reintentamos.
      const armarWatchdog = (ms: number) => {
        if (watchdog) clearTimeout(watchdog);
        watchdog = setTimeout(() => {
          alCerrar();
          socket.close();
        }, ms);
      };

      armarWatchdog(CONEXION_MS);

      socket.onopen = () => {
        if (!activo || ws !== socket) return;
        reintentos = 0;
        setConectado(true);
        detenerPolling();
        armarWatchdog(SIN_NOTICIAS_MS);
      };

      socket.onmessage = (evento) => {
        if (!activo || ws !== socket) return;
        armarWatchdog(SIN_NOTICIAS_MS);
        try {
          const msg = JSON.parse(evento.data);
          if (msg.tipo === 'estado') setPedido(msg.pedido);
        } catch {
          // mensaje ilegible: se ignora
        }
      };

      socket.onclose = (evento) => alCerrar(evento.code);
      socket.onerror = () => {
        socket.onerror = null; // close() puede volver a disparar 'error': evita el bucle
        alCerrar();
        socket.close();
      };
    };

    conectar();

    // Al volver a primer plano: refrescar ya y reconectar sin esperar el backoff
    const suscripcion = AppState.addEventListener('change', (estadoApp) => {
      if (estadoApp !== 'active' || !activo) return;
      cargarPorHttp();
      if (!ws || ws.readyState === WebSocket.CLOSED) {
        if (timerReconexion) clearTimeout(timerReconexion);
        reintentos = 0;
        conectar();
      }
    });

    return () => {
      activo = false;
      suscripcion.remove();
      if (timerReconexion) clearTimeout(timerReconexion);
      if (watchdog) clearTimeout(watchdog);
      detenerPolling();
      if (ws) {
        ws.onclose = null;
        ws.onmessage = null;
        ws.onerror = null;
        ws.close();
      }
      setConectado(false);
    };
  }, [idPedido, finalizado]);

  return { pedido, conectado, noExiste };
}
