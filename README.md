# ☕ Cafetería UMG - Sistema de Gestión de Pedidos
> **Digitalizing the university snack bar experience with a Full-Stack approach.**

![React Native](https://img.shields.io/badge/React_Native-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![MySQL](https://img.shields.io/badge/MySQL-00000f?style=for-the-badge&logo=mysql&logoColor=white)
![Expo](https://img.shields.io/badge/Expo-000020?style=for-the-badge&logo=expo&logoColor=white)

---

## 🇪🇸 Resumen del Proyecto (Spanish)
Este sistema permite a los estudiantes de la **Universidad Marista de Guadalajara** realizar pedidos desde su dispositivo móvil. La aplicación requiere identificación estudiantil (nombre y matrícula numérica de 6 dígitos), separa automáticamente el menú en **Comidas** y **Bebidas**, y gestiona las órdenes en tiempo real mediante una base de datos centralizada en MySQL y WebSockets.

### 🛠️ Arquitectura Técnica
- **Base de Datos:** MySQL (XAMPP) para persistencia de datos con pool de conexiones.
- **Backend:** API REST y WebSockets construidos con FastAPI (Python).
- **Frontend:** Aplicación móvil desarrollada en React Native con Expo Go (SDK 58).

---

## 🇺🇸 Project Overview (English)
A Full-Stack ordering system designed for university students. It features a gated institutional login screen (6-digit student ID validation), a modern UMG-branded mobile UI with smooth animations, and real-time order tracking connected directly to the kitchen display system (KDS).

### 🌟 Key Features
- **Student Authentication Gate:** Mandatory login with name and 6-digit numeric student ID before accessing the menu or order tracker.
- **Real-time synchronization** via WebSockets between the mobile app, MySQL database, and kitchen KDS.
- **Modern Institutional UI:** UMG visual identity (`#0F294A` & `#F59E0B`), skeleton loaders, animated category tabs, and haptic feedback.
- **Mouse-Friendly Kitchen KDS (`/admin`):** Real-time order tickets, payment method badges (`Efectivo` / `Tarjeta`), sound alerts, and 1-click complete/delete actions.

---

## 🚀 Guía de Ejecución / Execution Guide

### 1. Backend Setup (Terminal 1)
    # Navegar a la carpeta / Navigate to folder
    cd backend_api    

    # Activar entorno virtual / Activate venv
    .\.venv\Scripts\activate

    # Instalar dependencias (incluye 'websockets' para el tiempo real)
    pip install -r requirements.txt

    # Iniciar servidor / Start Server
    python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

Panel de cocina (KDS): abre `http://<IP-de-tu-PC>:8000/admin` en el navegador de la cocina.

### 2. Frontend Setup (Terminal 2)
    # Navegar a la carpeta / Navigate to folder
    cd app_estudiantes

    # Instalar dependencias / Install dependencies
    npm install

    # Iniciar Expo / Start Expo
    npx expo start -c

### ⚠️ Troubleshooting / Solución de Problemas

| Error | Cause / Causa | Solution / Solución |
| :--- | :--- | :--- |
| **Network Request Failed** | IP mismatch (IP cambió) | Update `API_URL` in `constants/api.ts` with your current IPv4. |
| **AbortError** | Server Offline (Servidor apagado) | Ensure the Python terminal shows "Application startup complete". |
| **No module named uvicorn** | Venv issues (Entorno virtual) | Run `pip install -r requirements.txt`. |
| **"No supported WebSocket library detected"** | Falta `websockets` | `pip install "uvicorn[standard]"` (la app sigue funcionando por polling, pero sin avisos instantáneos). |
| **La app no encuentra el servidor** | IP distinta | La app detecta la IP de tu PC sola; si usas `--tunnel`, crea `app_estudiantes/.env` con `EXPO_PUBLIC_API_URL=http://TU_IP:8000`. |
| **Connection Refused** | Firewall blocking (Bloqueo) | Disable Windows Firewall or add an inbound rule for port 8000. |
| **Project is incompatible with Expo Go** | SDK mismatch | Run `npx expo install --fix` inside `app_estudiantes`. |

---

## 🔔 Seguimiento del pedido en tiempo real

Estados en la BD → lo que ve el alumno:

| BD (`Pedidos.estado`) | App del alumno |
| :--- | :--- |
| `En Cola` | Orden recibida en cocina |
| `Preparando` | Preparando tus alimentos |
| `Listo` | ¡Listo para recoger! |
| `Entregado` | Pedido entregado |

- La cocina cambia el estado con `PUT /pedido/{id}/estado` o elimina órdenes canceladas con `DELETE /pedido/{id}`.
- El servidor avisa por **WebSocket** (`/ws/pedido/{id}` para el alumno, `/ws/cocina` para el KDS).
- Si el WebSocket falla, la app consulta `GET /pedido/{id}` cada 4 s (respaldo por polling).
- Pruebas del backend: `cd backend_api && python -m pytest test_tiempo_real.py -v`

---

## 📊 Database Schema (SQL)
El sistema utiliza una estructura relacional de tres tablas principales:

- **Productos:** Catálogo de alimentos y bebidas.
- **Pedidos:** Cabecera de la orden con nombre, matrícula, método de pago y total.
- **Detalle_Pedidos:** Desglose de productos por orden.

---

## 📝 UPDATES

- Base de datos actualizada con los precios reales de la cafetería y pool de conexiones en MySQL.
- Control de estados en tiempo real vía WebSockets y soporte para múltiples pedidos simultáneos.
- Expo migrado a SDK 58 con nueva identidad visual institucional (Universidad Marista de Guadalajara), animaciones nativas, *skeleton loaders* y vibración háptica.
- Pantalla de acceso obligatorio con validación de matrícula numérica de 6 dígitos antes de acceder al menú o al seguimiento.
- Panel KDS (`/admin`) renovado para operación 100% con mouse: método de pago visible, alertas sonoras, reloj en vivo y botones directos de finalizar/eliminar.

---

**Developed by:** Rodrigo Martínez Martínez, Ulises Josell Gonzales Lopez
**Major:** Ingeniería en Cibernética (8vo Semestre)  
**Institution:** Universidad Marista de Guadalajara (UMG)  

*IT'S NOT FINISHED YET*