#☕ Cafetería UMG - Sistema de Pedidos Full-Stack

Este proyecto es un sistema de pedidos en tiempo real que conecta una aplicación móvil (React Native/Expo) con una base de datos MySQL a través de una API construida con Python (FastAPI).

🚀 Guía de Inicio Rápido
Para que el sistema funcione, es necesario tener dos terminales abiertas simultáneamente en VS Code.

Terminal 1: Backend (El Cerebro) 🧠
Esta terminal gestiona la conexión con la base de datos y procesa los pedidos.

Navega a la carpeta: cd backend_api

Activa el entorno virtual: .\.venv\Scripts\activate

Inicia el servidor: ```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000

*Nota: El `--host 0.0.0.0` es vital para permitir que dispositivos externos (tu celular) se conecten a la PC.*

Terminal 2: Frontend (La App) 📱
Esta terminal compila la interfaz que ve el estudiante.

Navega a la carpeta: cd app_estudiantes

Inicia Expo:

Bash
npx expo start --tunnel
Nota: Usamos --tunnel para saltar restricciones de red y facilitar la conexión con Expo Go.

🛠️ Solución de Problemas (Troubleshooting)
Si la app inicia pero no ves los productos o marca error de conexión, revisa estos puntos que son los fallos más comunes:

1. Dirección IP Desactualizada (Error: Network Request Failed)
Las IPs locales cambian. Si la app no carga:

Abre una terminal y escribe ipconfig.

Copia tu Dirección IPv4 actual.

En app_estudiantes/app/(tabs)/index.tsx, actualiza la constante API_URL:

JavaScript
const API_URL = 'http://TU_NUEVA_IP:8000';
2. Firewall de Windows
A veces Windows bloquea la entrada del celular aunque la IP sea correcta.

Solución: Desactiva temporalmente el Firewall de Windows o crea una regla de entrada para el puerto 8000.

3. Estado de MySQL (XAMPP)
Si el backend marca errores de conexión:

Asegúrate de que el módulo MySQL en XAMPP esté en verde.

Verifica que la tabla Productos tenga datos insertados, de lo contrario la app dirá "No hay productos en esta categoría".

4. Entorno Virtual de Python
Si recibes el error No module named uvicorn:

Asegúrate de que el entorno esté activo (debe aparecer (.venv) en la terminal).

Si persiste, reinstala las dependencias: pip install fastapi uvicorn mysql-connector-python.

📋 Requisitos del Sistema
Python 3.10+

Node.js & npm

XAMPP (para el servidor MySQL)

Expo Go instalado en el dispositivo móvil.

📸 Avances del Proyecto
Actualmente, el sistema ya permite filtrar por Comida y Bebidas, registrar el nombre del estudiante y enviar la orden directamente a la base de datos MySQL.
