import AsyncStorage from '@react-native-async-storage/async-storage';
import * as Haptics from 'expo-haptics';
import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';
import { Alert, Platform, Vibration } from 'react-native';

import { EstadoPedido, Pedido, useOrderStatus } from '@/hooks/use-order-status';

const STORAGE_KEY = 'pedido_activo_id';

interface ActiveOrderContextValue {
  /** Último estado conocido del pedido que se está siguiendo (null si no hay) */
  pedido: Pedido | null;
  idPedido: number | null;
  /** true = WebSocket abierto ("en vivo"); false = respaldo por polling */
  conectado: boolean;
  /** false mientras se lee el pedido guardado en el teléfono */
  listo: boolean;
  iniciarSeguimiento: (id: number) => Promise<void>;
  terminarSeguimiento: () => Promise<void>;
}

const ActiveOrderContext = createContext<ActiveOrderContextValue | null>(null);

/** Vibración / háptico + aviso al cambiar de estado (no se dispara en la primera carga) */
function avisarCambio(nuevo: EstadoPedido, idPedido: number) {
  if (nuevo === 'Listo') {
    Haptics.notificationAsync(Haptics.NotificationFeedbackType.Success).catch(() => {});
    if (Platform.OS === 'android') Vibration.vibrate([0, 400, 200, 400]);
    Alert.alert(
      '🎉 ¡Tu pedido está listo!',
      `Pasa a la barra a recoger tu orden #${idPedido}.`,
    );
  } else if (nuevo === 'Preparando') {
    Haptics.impactAsync(Haptics.ImpactFeedbackStyle.Medium).catch(() => {});
  }
}

export function ActiveOrderProvider({ children }: { children: React.ReactNode }) {
  const [idPedido, setIdPedido] = useState<number | null>(null);
  const [listo, setListo] = useState(false);

  // Recupera el pedido en curso si el alumno cerró y volvió a abrir la app
  useEffect(() => {
    AsyncStorage.getItem(STORAGE_KEY)
      .then((guardado) => {
        const id = guardado ? Number(guardado) : NaN;
        if (Number.isInteger(id) && id > 0) setIdPedido(id);
      })
      .catch(() => {})
      .finally(() => setListo(true));
  }, []);

  const { pedido, conectado, noExiste } = useOrderStatus(idPedido);

  const iniciarSeguimiento = useCallback(async (id: number) => {
    setIdPedido(id);
    await AsyncStorage.setItem(STORAGE_KEY, String(id)).catch(() => {});
  }, []);

  const terminarSeguimiento = useCallback(async () => {
    setIdPedido(null);
    await AsyncStorage.removeItem(STORAGE_KEY).catch(() => {});
  }, []);

  // Pedido guardado que ya no existe en el servidor (p. ej. se reinició la BD)
  useEffect(() => {
    if (noExiste) terminarSeguimiento();
  }, [noExiste, terminarSeguimiento]);

  // Detecta transiciones reales de estado
  const ultimoEstado = useRef<{ id: number; estado: EstadoPedido } | null>(null);
  useEffect(() => {
    if (!pedido) {
      ultimoEstado.current = null;
      return;
    }
    const previo = ultimoEstado.current;
    ultimoEstado.current = { id: pedido.id_pedido, estado: pedido.estado };
    if (previo && previo.id === pedido.id_pedido && previo.estado !== pedido.estado) {
      avisarCambio(pedido.estado, pedido.id_pedido);
    }
  }, [pedido]);

  const value = useMemo(
    () => ({ pedido, idPedido, conectado, listo, iniciarSeguimiento, terminarSeguimiento }),
    [pedido, idPedido, conectado, listo, iniciarSeguimiento, terminarSeguimiento],
  );

  return <ActiveOrderContext.Provider value={value}>{children}</ActiveOrderContext.Provider>;
}

export function useActiveOrder() {
  const ctx = useContext(ActiveOrderContext);
  if (!ctx) throw new Error('useActiveOrder debe usarse dentro de <ActiveOrderProvider>');
  return ctx;
}
