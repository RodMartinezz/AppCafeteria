# ☕ Cafetería UMG - Sistema de Gestión de Pedidos
> **Digitalizing the university snack bar experience with a Full-Stack approach.**

![React Native](https://img.shields.io/badge/React_Native-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![MySQL](https://img.shields.io/badge/MySQL-00000f?style=for-the-badge&logo=mysql&logoColor=white)
![Expo](https://img.shields.io/badge/Expo-000020?style=for-the-badge&logo=expo&logoColor=white)

---

## 🇪🇸 Resumen del Proyecto (Spanish)
Este sistema permite a los estudiantes de la **Universidad Marista de Guadalajara** realizar pedidos desde su dispositivo móvil. La aplicación separa automáticamente el menú en **Comidas** y **Bebidas**, gestionando las órdenes en tiempo real mediante una base de datos centralizada en MySQL.

### 🛠️ Arquitectura Técnica
* **Base de Datos:** MySQL (XAMPP) para persistencia de datos.
* **Backend:** API REST construida con FastAPI (Python).
* **Frontend:** Aplicación móvil desarrollada en React Native con Expo Go.

---

## 🇺🇸 Project Overview (English)
A Full-Stack ordering system designed for university students. It features a clean, tab-based interface to browse products, manage a shopping cart, and send orders directly to the kitchen staff via a robust Python backend.

### 🌟 Key Features
* **Real-time synchronization** between mobile app and MySQL database.
* **Category filtering** (Food vs. Drinks) for better UX.
* **Identifier-based ordering** using name or student ID.

---

## 🚀 Guía de Ejecución / Execution Guide

### 1. Backend Setup (Terminal 1)
```bash
# Navegar a la carpeta / Navigate to folder
cd backend_api    



# Activar entorno virtual / Activate venv
.\.venv\Scripts\activate

# Instalar dependencias (incluye 'websockets' para el tiempo real)
pip install -r requirements.txt

# Iniciar servidor / Start Server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Panel de cocina (KDS): abre `http://<IP-de-tu-PC>:8000/admin` en el navegador de la cocina.
### 2. Frontend Setup (Terminal 2)
```bash
# Navegar a la carpeta / Navigate to folder
cd app_estudiantes

# Iniciar Expo con túnel / Start Expo with tunnel
npx expo start --tunnel
```
### ⚠️ Troubleshooting / Solución de Problemas

| Error | Cause / Causa | Solution / Solución |
| :--- | :--- | :--- |
| **Network Request Failed** | IP mismatch (IP cambió) | Update `API_URL` in `index.tsx` with your current IPv4. |
| **AbortError** | Server Offline (Servidor apagado) | Ensure the Python terminal shows "Application startup complete". |
| **No module named uvicorn** | Venv issues (Entorno virtual) | Run `pip install -r requirements.txt`. |
| **"No supported WebSocket library detected"** | Falta `websockets` | `pip install "uvicorn[standard]"` (la app sigue funcionando por polling, pero sin avisos instantáneos). |
| **La app no encuentra el servidor** | IP distinta | La app detecta la IP de tu PC sola; si usas `--tunnel`, crea `app_estudiantes/.env` con `EXPO_PUBLIC_API_URL=http://TU_IP:8000`. |
| **Connection Refused** | Firewall blocking (Bloqueo) | Disable Windows Firewall or add an inbound rule for port 8000. |




## 🔔 Seguimiento del pedido en tiempo real

Estados en la BD → lo que ve el alumno:

| BD (`Pedidos.estado`) | App del alumno |
| :--- | :--- |
| `En Cola` | Pendiente |
| `Preparando` | En preparación |
| `Listo` | Listo para recoger |
| `Entregado` | Entregado |

* La cocina cambia el estado con `PUT /pedido/{id}/estado` (solo se permite avanzar/corregir un paso a la vez).
* El servidor avisa por **WebSocket** (`/ws/pedido/{id}` para el alumno, `/ws/cocina` para el KDS).
* Si el WebSocket falla, la app consulta `GET /pedido/{id}` cada 4 s (respaldo por polling).
* Pruebas del backend: `cd backend_api && python -m pytest test_tiempo_real.py -v`

📊 Database Schema (SQL)
El sistema utiliza una estructura relacional de tres tablas principales:

Productos: Catálogo de alimentos y bebidas.

Pedidos: Cabecera de la orden con nombre y total.

Detalle_Pedidos: Desglose de productos por orden.

Developed by: Rodrigo Martínez Martínez

Major: Ingeniería en Cibernética (8vo Semestre)

##UPDATES

esta nueva version ya cuenta con la base de datos con los precios reales de la cafeteria
ya cuenta con orden de pedidos para tener un mejor control de lo que se pide y quien
la bd no colapsa con mas de 5 pedidos
expo actualizado a la ultima version

Institution: Universidad Marista de Guadalajara (UMG)

ITS NOT FINISH YET
