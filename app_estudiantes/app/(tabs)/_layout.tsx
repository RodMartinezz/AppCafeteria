import { Tabs } from 'expo-router';
import React from 'react';

import { HapticTab } from '@/components/haptic-tab';
import { IconSymbol } from '@/components/ui/icon-symbol';
import { Colors } from '@/constants/theme';
import { useActiveOrder } from '@/context/active-order';
import { useColorScheme } from '@/hooks/use-color-scheme';

export default function TabLayout() {
  const colorScheme = useColorScheme();
  const { pedido } = useActiveOrder();

  // Puntito en la pestaña "Mi pedido" cuando el pedido está listo para recoger
  const listoParaRecoger = pedido?.estado === 'Listo';

  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: Colors[colorScheme ?? 'light'].tint,
        headerShown: false,
        tabBarButton: HapticTab,
      }}>
      <Tabs.Screen
        name="index"
        options={{
          title: 'Menú',
          tabBarIcon: ({ color }) => <IconSymbol size={28} name="fork.knife" color={color} />,
        }}
      />
      <Tabs.Screen
        name="mi-pedido"
        options={{
          title: 'Mi pedido',
          tabBarBadge: listoParaRecoger ? '!' : undefined,
          tabBarIcon: ({ color }) => <IconSymbol size={28} name="bag.fill" color={color} />,
        }}
      />
    </Tabs>
  );
}
