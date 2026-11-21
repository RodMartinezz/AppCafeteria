import { useRouter } from 'expo-router';
import React, { useEffect, useState } from 'react';
import { ActivityIndicator, Animated, ScrollView, StyleSheet, Text, TouchableOpacity, View } from 'react-native';

import { useActiveOrder } from '@/context/active-order';
import { EstadoPedido } from '@/hooks/use-order-status';

// El nombre del estado en la BD y lo que ve el alumno no tienen por qué coincidir
const ORDEN: EstadoPedido[] = ['En Cola', 'Preparando', 'Listo', 'Entregado'];

const INFO: Record<EstadoPedido, { emoji: string; titulo: string; detalle: string; color: string }> = {
  'En Cola': {
    emoji: '🕐',
    titulo: 'Pedido recibido',
    detalle: 'La cocina ya lo tiene. En cuanto lo tomen verás el cambio aquí.',
    color: '#FF9500',
  },
  Preparando: {
    emoji: '👨‍🍳',
    titulo: 'En preparación',
    detalle: 'Tu pedido se está preparando. ¡Ya falta poco!',
    color: '#007AFF',
  },
  Listo: {
    emoji: '✅',
    titulo: '¡Listo para recoger!',
    detalle: 'Pasa a la barra y muestra tu número de orden.',
    color: '#34C759',
  },
  Entregado: {
    emoji: '🎉',
    titulo: 'Pedido entregado',
    detalle: '¡Buen provecho!',
    color: '#8E8E93',
  },
};

const PASOS: { estado: EstadoPedido; nombre: string }[] = [
  { estado: 'En Cola', nombre: 'Pendiente' },
  { estado: 'Preparando', nombre: 'En preparación' },
  { estado: 'Listo', nombre: 'Listo para recoger' },
];

/** Círculo que late suavemente: marca el paso en el que va el pedido */
function PuntoActivo({ color }: { color: string }) {
  const [escala] = useState(() => new Animated.Value(1));

  useEffect(() => {
    const animacion = Animated.loop(
      Animated.sequence([
        Animated.timing(escala, { toValue: 1.2, duration: 700, useNativeDriver: true }),
        Animated.timing(escala, { toValue: 1, duration: 700, useNativeDriver: true }),
      ]),
    );
    animacion.start();
    return () => animacion.stop();
  }, [escala]);

  return (
    <Animated.View style={[styles.punto, { backgroundColor: color, transform: [{ scale: escala }] }]}>
      <View style={styles.puntoInterno} />
    </Animated.View>
  );
}

function Pasos({ estado }: { estado: EstadoPedido }) {
  const indiceActual = ORDEN.indexOf(estado);

  return (
    <View style={styles.pasos}>
      {PASOS.map((paso, i) => {
        const hecho = i < indiceActual || estado === 'Entregado';
        const actual = i === indiceActual && estado !== 'Entregado';
        const color = INFO[paso.estado].color;

        return (
          <View key={paso.estado} style={styles.pasoFila}>
            <View style={styles.pasoColumnaIcono}>
              {actual ? (
                <PuntoActivo color={color} />
              ) : (
                <View style={[styles.punto, { backgroundColor: hecho ? '#34C759' : '#E5E5EA' }]}>
                  {hecho && <Text style={styles.palomita}>✓</Text>}
                </View>
              )}
              {i < PASOS.length - 1 && (
                <View style={[styles.linea, { backgroundColor: hecho ? '#34C759' : '#E5E5EA' }]} />
              )}
            </View>
            <Text
              style={[
                styles.pasoTexto,
                actual && { color, fontWeight: '700' },
                hecho && { color: '#1C1C1E' },
              ]}>
              {paso.nombre}
            </Text>
          </View>
        );
      })}
    </View>
  );
}

export function OrderTracker() {
  const router = useRouter();
  const { pedido, idPedido, conectado, listo, terminarSeguimiento } = useActiveOrder();

  if (!listo || (idPedido != null && !pedido)) {
    return (
      <View style={styles.centro}>
        <ActivityIndicator size="large" color="#007AFF" />
        <Text style={styles.centroTexto}>Consultando tu pedido…</Text>
      </View>
    );
  }

  if (!pedido) {
    return (
      <View style={styles.centro}>
        <Text style={styles.emojiGrande}>🍽️</Text>
        <Text style={styles.centroTitulo}>No tienes pedidos en curso</Text>
        <Text style={styles.centroTexto}>Cuando hagas un pedido, aquí verás cómo avanza en tiempo real.</Text>
        <TouchableOpacity style={styles.boton} onPress={() => router.navigate('/')}>
          <Text style={styles.botonTexto}>Ver el menú</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const info = INFO[pedido.estado];
  const entregado = pedido.estado === 'Entregado';

  return (
    <ScrollView contentContainerStyle={styles.contenido}>
      {/* Número de orden: es lo que se muestra en barra para recoger */}
      <View style={styles.encabezado}>
        <Text style={styles.encabezadoEtiqueta}>NÚMERO DE ORDEN</Text>
        <Text style={styles.numeroOrden}>#{pedido.id_pedido}</Text>
        <Text style={styles.encabezadoNombre}>{pedido.nombre_estudiante}</Text>
      </View>

      {/* Estado actual, bien grande */}
      <View style={[styles.estadoCaja, { backgroundColor: info.color + '1A', borderColor: info.color }]}>
        <Text style={styles.estadoEmoji}>{info.emoji}</Text>
        <Text style={[styles.estadoTitulo, { color: info.color }]}>{info.titulo}</Text>
        <Text style={styles.estadoDetalle}>{info.detalle}</Text>
        {pedido.estado === 'En Cola' && (
          <Text style={styles.cola}>
            {pedido.pedidos_antes === 0
              ? '🙌 Eres el siguiente'
              : `⏳ ${pedido.pedidos_antes} pedido${pedido.pedidos_antes === 1 ? '' : 's'} en espera antes que el tuyo`}
          </Text>
        )}
      </View>

      <Pasos estado={pedido.estado} />

      {/* Resumen */}
      <View style={styles.resumen}>
        <Text style={styles.resumenTitulo}>Tu pedido</Text>
        {pedido.items.map((item, i) => (
          <View key={i} style={styles.resumenFila}>
            <Text style={styles.resumenItem}>
              {item.cantidad}× {item.nombre}
            </Text>
          </View>
        ))}
        <View style={styles.resumenTotal}>
          <Text style={styles.resumenTotalTexto}>
            Total ({pedido.metodo_pago ?? 'pago en caja'})
          </Text>
          <Text style={styles.resumenTotalTexto}>${Number(pedido.total).toFixed(2)}</Text>
        </View>
      </View>

      {!entregado && (
        <Text style={[styles.conexion, { color: conectado ? '#248A3D' : '#C77700' }]}>
          {conectado ? '🟢 En vivo' : '🟠 Reconectando… (revisando cada 4 s)'}
        </Text>
      )}

      {entregado && (
        <TouchableOpacity
          style={styles.boton}
          onPress={async () => {
            await terminarSeguimiento();
            router.navigate('/');
          }}>
          <Text style={styles.botonTexto}>Hacer otro pedido</Text>
        </TouchableOpacity>
      )}
    </ScrollView>
  );
}

const styles = StyleSheet.create({
  contenido: { padding: 20, paddingBottom: 40 },
  centro: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 30 },
  centroTitulo: { fontSize: 20, fontWeight: '700', marginTop: 10, textAlign: 'center' },
  centroTexto: { color: '#666', textAlign: 'center', marginTop: 8, marginBottom: 20 },
  emojiGrande: { fontSize: 56 },

  encabezado: { alignItems: 'center', marginBottom: 16 },
  encabezadoEtiqueta: { fontSize: 12, letterSpacing: 1.5, color: '#8E8E93', fontWeight: '600' },
  numeroOrden: { fontSize: 56, fontWeight: '800', color: '#1C1C1E' },
  encabezadoNombre: { color: '#666', fontSize: 15 },

  estadoCaja: { borderWidth: 2, borderRadius: 18, padding: 20, alignItems: 'center', marginBottom: 20 },
  estadoEmoji: { fontSize: 44 },
  estadoTitulo: { fontSize: 24, fontWeight: '800', marginTop: 6, textAlign: 'center' },
  estadoDetalle: { color: '#444', textAlign: 'center', marginTop: 6, fontSize: 15 },
  cola: { marginTop: 12, fontWeight: '600', color: '#1C1C1E' },

  pasos: { backgroundColor: '#fff', borderRadius: 14, padding: 18, marginBottom: 20, elevation: 2 },
  pasoFila: { flexDirection: 'row', alignItems: 'flex-start', minHeight: 56 },
  pasoColumnaIcono: { width: 36, alignItems: 'center' },
  punto: { width: 26, height: 26, borderRadius: 13, alignItems: 'center', justifyContent: 'center' },
  puntoInterno: { width: 10, height: 10, borderRadius: 5, backgroundColor: '#fff' },
  palomita: { color: '#fff', fontWeight: '800', fontSize: 14 },
  linea: { width: 3, flex: 1, marginVertical: 2, borderRadius: 2 },
  pasoTexto: { marginLeft: 10, marginTop: 3, fontSize: 16, color: '#8E8E93' },

  resumen: { backgroundColor: '#fff', borderRadius: 14, padding: 18, elevation: 2 },
  resumenTitulo: { fontWeight: '700', fontSize: 16, marginBottom: 8 },
  resumenFila: { paddingVertical: 3 },
  resumenItem: { fontSize: 15, color: '#333' },
  resumenTotal: {
    flexDirection: 'row',
    justifyContent: 'space-between',
    borderTopWidth: 1,
    borderTopColor: '#eee',
    marginTop: 10,
    paddingTop: 10,
  },
  resumenTotalTexto: { fontWeight: '700', fontSize: 15 },

  conexion: { textAlign: 'center', marginTop: 16, fontSize: 13, fontWeight: '600' },

  boton: { backgroundColor: '#34C759', paddingVertical: 16, paddingHorizontal: 28, borderRadius: 14, alignItems: 'center', marginTop: 20 },
  botonTexto: { color: '#fff', fontWeight: '700', fontSize: 16 },
});
