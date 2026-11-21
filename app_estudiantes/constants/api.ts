import Constants from 'expo-constants';

/**
 * Dirección del backend FastAPI. Se resuelve en este orden:
 *  1. Variable EXPO_PUBLIC_API_URL (archivo .env en app_estudiantes), p. ej.:
 *       EXPO_PUBLIC_API_URL=http://192.168.100.182:8000
 *  2. La IP de la computadora que corre Expo (funciona sin tocar nada cuando
 *     FastAPI y Expo están en la misma PC y usas `npx expo start` por LAN).
 *  3. IP fija de respaldo (ajústala si cambia tu red).
 *
 * Nota: con `--tunnel` el host de Expo es un dominio exp.direct, no sirve para
 * llegar al backend; en ese caso se usa la opción 1 o 3.
 */
const IP_FIJA_RESPALDO = 'http://127.0.0.1:8000';
const PUERTO_API = 8000;

function resolverApiUrl(): string {
  const desdeEnv = process.env.EXPO_PUBLIC_API_URL;
  if (desdeEnv) return desdeEnv.replace(/\/$/, '');

  const hostUri = Constants.expoConfig?.hostUri; // p. ej. "192.168.100.182:8081"
  const host = hostUri?.split(':')[0];
  if (host && /^\d{1,3}(\.\d{1,3}){3}$/.test(host)) {
    return `http://${host}:${PUERTO_API}`;
  }
  return IP_FIJA_RESPALDO;
}

export const API_URL = resolverApiUrl();
export const WS_URL = API_URL.replace(/^http/, 'ws');
