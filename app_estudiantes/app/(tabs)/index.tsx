import React, { useState, useEffect, useCallback } from 'react';
import { 
  View, 
  Text, 
  FlatList, 
  TouchableOpacity, 
  StyleSheet, 
  TextInput, 
  Alert, 
  Modal, 
  ActivityIndicator,
  AppState
} from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';
import { useRouter, useFocusEffect } from 'expo-router';

import { API_URL } from '@/constants/api';
import { useActiveOrder } from '@/context/active-order';

interface Producto {
  id_producto: number;
  nombre: string;
  precio: string | number;
  categoria: 'Comida' | 'Bebida';
}

const REFRESCO_MENU_MS = 30000; // el admin puede cambiar precios/disponibilidad en cualquier momento

// "Café" == "cafe": búsqueda sin acentos ni mayúsculas
const normalizar = (t: string) =>
  t.normalize('NFD').replace(/[\u0300-\u036f]/g, '').toLowerCase().trim();

const ETIQUETA_ESTADO: Record<string, string> = {
  'En Cola': 'Pendiente',
  'Preparando': 'En preparación',
  'Listo': '¡Listo para recoger!',
};

export default function App() {
  const router = useRouter();
  const { pedido: pedidoActivo, iniciarSeguimiento } = useActiveOrder();
  const [menu, setMenu] = useState<Producto[]>([]);
  const [filtro, setFiltro] = useState('Comida');
  const [nombre, setNombre] = useState('');
  const [matricula, setMatricula] = useState('');
  const [carrito, setCarrito] = useState<Producto[]>([]);
  const [errorDebug, setErrorDebug] = useState<string | null>(null);
  const [modalVisible, setModalVisible] = useState(false);
  const [metodoPago, setMetodoPago] = useState('Efectivo');
  const [enviando, setEnviando] = useState(false);
  const [busqueda, setBusqueda] = useState('');
  const [menuCargado, setMenuCargado] = useState(false);
  const [refrescando, setRefrescando] = useState(false);
  const [avisoCarrito, setAvisoCarrito] = useState<string | null>(null);

  // silencioso = refresco automático: no parpadea el aviso de "Intentando conectar..."
  const cargarDatos = useCallback(async (silencioso = false) => {
    try {
      if (!silencioso) setErrorDebug("Intentando conectar...");
      const res = await fetch(`${API_URL}/menu`);
      if (!res.ok) throw new Error(`El servidor respondió ${res.status}`);
      const d = await res.json();
      setMenu(d.menu || []);
      setMenuCargado(true);
      setErrorDebug(null);
    } catch (e: any) {
      // En un refresco automático solo avisamos si todavía no hay menú que mostrar
      if (!silencioso || !menuCargado) setErrorDebug("ERROR DE CONEXIÓN: " + e.message);
    }
  }, [menuCargado]);

  // Menú al día: al abrir la pestaña, cada 30 s mientras está a la vista y al volver a la app
  useFocusEffect(
    useCallback(() => {
      cargarDatos();
      const timer = setInterval(() => cargarDatos(true), REFRESCO_MENU_MS);
      const suscripcion = AppState.addEventListener('change', (estado) => {
        if (estado === 'active') cargarDatos(true);
      });
      return () => {
        clearInterval(timer);
        suscripcion.remove();
      };
    }, [cargarDatos])
  );

  const alRefrescar = async () => {
    setRefrescando(true);
    await cargarDatos(true);
    setRefrescando(false);
  };

  // Si el admin cambió un precio o apagó un producto, el carrito se corrige solo y se avisa
  useEffect(() => {
    if (!menuCargado) return;
    const vigentes = new Map(menu.map(p => [p.id_producto, p]));
    let quitados = 0;
    let cambiados = 0;
    const nuevo: Producto[] = [];
    for (const item of carrito) {
      const vigente = vigentes.get(item.id_producto);
      if (!vigente) { quitados++; continue; }
      if (Number(vigente.precio) !== Number(item.precio)) cambiados++;
      nuevo.push(vigente);
    }
    if (quitados || cambiados) {
      setCarrito(nuevo);
      const partes = [];
      if (cambiados) partes.push(`${cambiados} producto(s) cambiaron de precio`);
      if (quitados) partes.push(`${quitados} ya no está(n) disponible(s)`);
      setAvisoCarrito('Actualizamos tu carrito: ' + partes.join(' y ') + '.');
    }
  }, [menu, menuCargado, carrito]);

  // [Café, Café, Torta] -> [{Café x2}, {Torta x1}]
  const agruparCarrito = (productos: { id_producto: number }[]) => {
    const porId: Record<number, number> = {};
    productos.forEach(p => {
      porId[p.id_producto] = (porId[p.id_producto] || 0) + 1;
    });
    return Object.entries(porId).map(([id, cantidad]) => ({
      id_producto: Number(id),
      cantidad,
      notas: ""
    }));
  };

  const totalCarrito = carrito.reduce((acc, item) => acc + Number(item.precio), 0);

  const abrirModalPago = () => {
    if (!nombre.trim()) {
      return Alert.alert("Falta Nombre", "Por favor ingresa tu nombre completo.");
    }
    if (!matricula.trim()) {
      return Alert.alert("Falta Matrícula", "Por favor ingresa tu matrícula de estudiante.");
    }
    if (carrito.length === 0) {
      return Alert.alert("Carrito Vacío", "Agrega al menos un producto a tu pedido.");
    }
    setModalVisible(true);
  };

  const procesarPedido = async () => {
    setEnviando(true);
    try {
      const res = await fetch(`${API_URL}/ordenar`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          nombre_estudiante: nombre.trim(),
          matricula: matricula.trim(),
          metodo_pago: metodoPago,
          items: agruparCarrito(carrito),
          // Lo que el alumno vio en pantalla: si el precio cambió, el servidor lo rechaza (409)
          total_esperado: Number(totalCarrito.toFixed(2))
        })
      });

      const d = await res.json();

      if (res.ok) {
        setModalVisible(false);
        // Guardamos el número de orden: desde aquí la app escucha los cambios de estado
        await iniciarSeguimiento(d.numero_orden);
        setCarrito([]);
        setNombre('');
        setMatricula('');
        setMetodoPago('Efectivo');
        router.navigate('/mi-pedido');
      } else {
        Alert.alert("Error", typeof d.detail === 'string' ? d.detail : "Revisa los datos de tu pedido.");
        // 409 = cambió un precio · 400 = un producto ya no está: se vuelve a leer el menú
        if (res.status === 409 || res.status === 400) {
          setModalVisible(false);
          cargarDatos(true);
        }
      }
    } catch {
      Alert.alert("Error", "No se pudo conectar con el servidor para enviar la orden.");
    } finally {
      setEnviando(false);
    }
  };

  return (
    <SafeAreaView style={styles.safe}>
      <Text style={styles.header}>Cafetería UMG ☕</Text>
      
      {/* Aviso de pedido en curso: toca para ver el seguimiento */}
      {pedidoActivo && pedidoActivo.estado !== 'Entregado' && (
        <TouchableOpacity
          style={[styles.bannerPedido, pedidoActivo.estado === 'Listo' && styles.bannerListo]}
          onPress={() => router.navigate('/mi-pedido')}
        >
          <Text style={styles.bannerTxt}>
            Pedido #{pedidoActivo.id_pedido}: {ETIQUETA_ESTADO[pedidoActivo.estado]}  ›
          </Text>
        </TouchableOpacity>
      )}

      {/* Sección de Depuración / Error */}
      {errorDebug && (
        <View style={styles.errorBox}>
          <Text style={styles.errorTxt}>{errorDebug}</Text>
          <TouchableOpacity onPress={() => cargarDatos()} style={styles.btnRetry}>
            <Text style={styles.txtRetry}>REINTENTAR CONEXIÓN</Text>
          </TouchableOpacity>
        </View>
      )}

      {/* Inputs de Datos de Alumno */}
      <TextInput 
        style={styles.input} 
        placeholder="Escribe tu Nombre..." 
        placeholderTextColor="#888"
        value={nombre} 
        onChangeText={setNombre} 
      />
      <TextInput 
        style={styles.input} 
        placeholder="Escribe tu Matrícula..." 
        placeholderTextColor="#888"
        keyboardType="numeric"
        value={matricula} 
        onChangeText={setMatricula} 
      />
      
      {/* Aviso cuando el admin cambió precios/disponibilidad de lo que ya estaba en el carrito */}
      {avisoCarrito && (
        <TouchableOpacity style={styles.avisoCarrito} onPress={() => setAvisoCarrito(null)}>
          <Text style={styles.avisoCarritoTxt}>⚠️ {avisoCarrito}  (toca para cerrar)</Text>
        </TouchableOpacity>
      )}

      {/* Buscador */}
      <TextInput
        style={styles.input}
        placeholder="🔍 Buscar producto..."
        placeholderTextColor="#888"
        value={busqueda}
        onChangeText={setBusqueda}
        autoCorrect={false}
        clearButtonMode="while-editing"
      />

      {/* Pestañas de Filtrado */}
      <View style={styles.tabs}>
        <TouchableOpacity 
          onPress={() => setFiltro('Comida')} 
          style={[styles.tab, filtro === 'Comida' && styles.tabActivo]}
        >
          <Text style={filtro === 'Comida' ? styles.txtActivo : styles.txtInactivo}>🍔 Comida</Text>
        </TouchableOpacity>
        <TouchableOpacity 
          onPress={() => setFiltro('Bebida')} 
          style={[styles.tab, filtro === 'Bebida' && styles.tabActivo]}
        >
          <Text style={filtro === 'Bebida' ? styles.txtActivo : styles.txtInactivo}>🥤 Bebidas</Text>
        </TouchableOpacity>
      </View>

      {/* Catálogo de Productos */}
      <FlatList
        data={menu.filter(item =>
          item.categoria === filtro &&
          (!busqueda.trim() || normalizar(item.nombre).includes(normalizar(busqueda)))
        )}
        keyExtractor={(item) => item.id_producto.toString()}
        refreshing={refrescando}
        onRefresh={alRefrescar}
        keyboardShouldPersistTaps="handled"
        ListEmptyComponent={
          <Text style={styles.empty}>
            {busqueda.trim() ? 'Ningún producto coincide con tu búsqueda.' : 'No hay productos en esta categoría.'}
          </Text>
        }
        renderItem={({ item }) => (
          <View style={styles.card}>
            <View style={{ flex: 1 }}>
              <Text style={styles.nom}>{item.nombre}</Text>
              <Text style={styles.precio}>${Number(item.precio).toFixed(2)}</Text>
            </View>
            <TouchableOpacity 
              onPress={() => setCarrito([...carrito, item])} 
              style={styles.btnAdd}
            >
              <Text style={styles.txtBtnAdd}>+ Pedir</Text>
            </TouchableOpacity>
          </View>
        )}
      />

      {/* Botón de Confirmación Principal */}
      <TouchableOpacity onPress={abrirModalPago} style={styles.btnOrder}>
        <Text style={styles.txtOrder}>
          Confirmar Pedido ({carrito.length}) • ${totalCarrito.toFixed(2)}
        </Text>
      </TouchableOpacity>

      {/* Modal de Selección de Método de Pago */}
      <Modal
        animationType="slide"
        transparent={true}
        visible={modalVisible}
        onRequestClose={() => setModalVisible(false)}
      >
        <View style={styles.modalOverlay}>
          <View style={styles.modalContent}>
            <Text style={styles.modalTitulo}>Método de Pago</Text>
            <Text style={styles.modalSubtitulo}>¿Cómo deseas liquidar en caja?</Text>

            {/* Opción Efectivo */}
            <TouchableOpacity 
              style={[styles.opcionPago, metodoPago === 'Efectivo' && styles.opcionSeleccionada]}
              onPress={() => setMetodoPago('Efectivo')}
            >
              <Text style={styles.opcionTexto}>💵 Efectivo</Text>
              <View style={[styles.radioCircle, metodoPago === 'Efectivo' && styles.radioSelected]} />
            </TouchableOpacity>

            {/* Opción Tarjeta */}
            <TouchableOpacity 
              style={[styles.opcionPago, metodoPago === 'Tarjeta' && styles.opcionSeleccionada]}
              onPress={() => setMetodoPago('Tarjeta')}
            >
              <Text style={styles.opcionTexto}>💳 Tarjeta (Terminal en caja)</Text>
              <View style={[styles.radioCircle, metodoPago === 'Tarjeta' && styles.radioSelected]} />
            </TouchableOpacity>

            {/* Botones de Acción del Modal */}
            <View style={styles.modalBotones}>
              <TouchableOpacity 
                style={styles.btnCancelar} 
                onPress={() => setModalVisible(false)}
                disabled={enviando}
              >
                <Text style={styles.txtCancelar}>Volver</Text>
              </TouchableOpacity>

              <TouchableOpacity 
                style={styles.btnAceptar} 
                onPress={procesarPedido}
                disabled={enviando}
              >
                {enviando ? (
                  <ActivityIndicator color="#fff" />
                ) : (
                  <Text style={styles.txtAceptar}>Finalizar</Text>
                )}
              </TouchableOpacity>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, padding: 20, backgroundColor: '#f9f9f9' },
  bannerPedido: { backgroundColor: '#007AFF', padding: 12, borderRadius: 10, marginBottom: 12 },
  bannerListo: { backgroundColor: '#34C759' },
  avisoCarrito: { backgroundColor: '#FFF4E5', borderColor: '#FF9500', borderWidth: 1, padding: 10, borderRadius: 10, marginBottom: 10 },
  avisoCarritoTxt: { color: '#8A4B00', fontSize: 13 },
  bannerTxt: { color: '#fff', fontWeight: '700', textAlign: 'center' },
  header: { fontSize: 26, fontWeight: 'bold', textAlign: 'center', marginBottom: 15 },
  errorBox: { backgroundColor: '#ffebee', padding: 10, borderRadius: 8, marginBottom: 12 },
  errorTxt: { color: 'red', textAlign: 'center', fontSize: 13 },
  btnRetry: { marginTop: 6, backgroundColor: 'red', padding: 6, borderRadius: 5 },
  txtRetry: { color: 'white', textAlign: 'center', fontWeight: 'bold', fontSize: 12 },
  input: { backgroundColor: '#fff', padding: 12, borderRadius: 10, borderWidth: 1, borderColor: '#ddd', marginBottom: 10, fontSize: 15 },
  tabs: { flexDirection: 'row', marginBottom: 15 },
  tab: { flex: 1, padding: 12, alignItems: 'center', borderBottomWidth: 3, borderBottomColor: '#eee' },
  tabActivo: { borderBottomColor: '#007AFF' },
  txtActivo: { color: '#007AFF', fontWeight: 'bold', fontSize: 16 },
  txtInactivo: { color: '#888', fontSize: 16 },
  card: { backgroundColor: '#fff', padding: 16, borderRadius: 12, marginBottom: 10, flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', elevation: 2 },
  nom: { fontSize: 16, fontWeight: '600' },
  precio: { color: '#007AFF', fontWeight: 'bold', marginTop: 4 },
  btnAdd: { backgroundColor: '#007AFF', paddingVertical: 8, paddingHorizontal: 14, borderRadius: 8 },
  txtBtnAdd: { color: '#fff', fontWeight: 'bold' },
  btnOrder: { backgroundColor: '#34C759', padding: 18, borderRadius: 15, alignItems: 'center', marginTop: 10 },
  txtOrder: { color: '#fff', fontWeight: 'bold', fontSize: 17 },
  empty: { textAlign: 'center', marginTop: 20, color: '#888' },

  /* Estilos del Modal */
  modalOverlay: { flex: 1, backgroundColor: 'rgba(0,0,0,0.5)', justifyContent: 'center', alignItems: 'center', padding: 20 },
  modalContent: { backgroundColor: '#fff', width: '100%', borderRadius: 16, padding: 20, elevation: 5 },
  modalTitulo: { fontSize: 20, fontWeight: 'bold', textAlign: 'center', marginBottom: 4 },
  modalSubtitulo: { fontSize: 14, textAlign: 'center', color: '#666', marginBottom: 18 },
  opcionPago: { flexDirection: 'row', justifyContent: 'space-between', alignItems: 'center', padding: 14, borderRadius: 10, borderWidth: 1, borderColor: '#ddd', marginBottom: 10 },
  opcionSeleccionada: { borderColor: '#007AFF', backgroundColor: '#f0f8ff' },
  opcionTexto: { fontSize: 15, fontWeight: '500' },
  radioCircle: { width: 20, height: 20, borderRadius: 10, borderWidth: 2, borderColor: '#888' },
  radioSelected: { borderColor: '#007AFF', backgroundColor: '#007AFF' },
  modalBotones: { flexDirection: 'row', marginTop: 15, gap: 10 },
  btnCancelar: { flex: 1, padding: 14, borderRadius: 10, backgroundColor: '#eee', alignItems: 'center' },
  txtCancelar: { color: '#333', fontWeight: '600' },
  btnAceptar: { flex: 1, padding: 14, borderRadius: 10, backgroundColor: '#34C759', alignItems: 'center' },
  txtAceptar: { color: '#fff', fontWeight: 'bold' }
});