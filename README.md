☕ Cafetería UMG - Sistema de Gestión de Pedidos
Este proyecto es una solución Full-Stack desarrollada para digitalizar el proceso de pedidos en la cafetería universitaria. Permite a los estudiantes visualizar el menú en tiempo real, filtrar por categorías y enviar órdenes directamente a una base de datos centralizada.

🛠️ Arquitectura del Sistema
El ecosistema funciona mediante la integración de tres capas tecnológicas:

Base de Datos (MySQL): Almacenamiento persistente de productos, pedidos y detalles de transacciones.

Backend (Python/FastAPI): API REST que gestiona la lógica de negocio, conexión a DB y comunicación con el cliente móvil.

Frontend (React Native/Expo): Aplicación móvil multiplataforma con interfaz intuitiva para el usuario.

🚀 Guía de Ejecución (Paso a Paso)
Para poner en marcha el sistema, es indispensable seguir este orden de encendido:

1. Preparar la Base de Datos 🗄️
Asegúrate de que el módulo MySQL esté activo en XAMPP.

Ejecuta el script de creación de tablas e inserta el catálogo inicial de productos.

2. Iniciar el Backend (Terminal 1) 🧠
Navega a la carpeta del servidor y activa el entorno virtual para garantizar la disponibilidad de las dependencias.

Bash
cd backend_api
.\.venv\Scripts\activate
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
Nota: Usar --host 0.0.0.0 es fundamental para que el servidor sea visible por el celular en la red local.

3. Iniciar la App (Terminal 2) 📱
Navega a la carpeta de la aplicación y arranca el entorno de desarrollo de Expo.

Bash
cd app_estudiantes
npx expo start --tunnel
⚠️ Solución de Fallos Comunes (Troubleshooting)
Si la aplicación no carga los productos o muestra errores de conexión (Network Request Failed), verifica estos puntos clave que solucionamos durante el desarrollo:

🔄 Sincronización de IP Local
Las direcciones IPv4 pueden cambiar al reconectar el equipo a la red.

Abre la terminal y ejecuta ipconfig.

Identifica tu Dirección IPv4 actual.

Actualiza la constante en app_estudiantes/app/(tabs)/index.tsx:

JavaScript
const API_URL = 'http://TU_NUEVA_IP:8000';
🛡️ Restricciones del Firewall
Windows Defender puede bloquear peticiones externas al puerto 8000.

Solución: Crea una regla de entrada para el puerto o desactiva temporalmente el Firewall durante las pruebas.

📦 Módulos de Python
Si el comando uvicorn no es reconocido, asegúrate de estar dentro del entorno virtual o reinstala las dependencias críticas:

Bash
pip install fastapi uvicorn mysql-connector-python
🎯 Funcionalidades Implementadas
[x] Persistencia de Datos: Conexión real con MySQL.

[x] Interfaz Dinámica: Navegación por pestañas (Comida / Bebidas).

[x] Gestión de Carrito: Selección de múltiples productos por orden.

[x] Identificación: Registro de pedidos por nombre o matrícula del alumno.

Desarrollado por: Rodrigo Martínez - Ingeniería en Cibernética
Institución: Universidad Marista de Guadalajara (UMG)
