import React from 'react';
import { StyleSheet, Text } from 'react-native';
import { SafeAreaView } from 'react-native-safe-area-context';

import { OrderTracker } from '@/components/order-tracker';

export default function MiPedidoScreen() {
  return (
    <SafeAreaView style={styles.safe} edges={['top']}>
      <Text style={styles.header}>Mi pedido</Text>
      <OrderTracker />
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  safe: { flex: 1, backgroundColor: '#f9f9f9' },
  header: { fontSize: 26, fontWeight: 'bold', textAlign: 'center', marginTop: 10 },
});
