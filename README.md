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

# Iniciar servidor / Start Server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
```
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
| **No module named uvicorn** | Venv issues (Entorno virtual) | Run `pip install fastapi uvicorn mysql-connector-python`. |
| **Connection Refused** | Firewall blocking (Bloqueo) | Disable Windows Firewall or add an inbound rule for port 8000. |




📊 Database Schema (SQL)
El sistema utiliza una estructura relacional de tres tablas principales:

Productos: Catálogo de alimentos y bebidas.

Pedidos: Cabecera de la orden con nombre y total.

Detalle_Pedidos: Desglose de productos por orden.

Developed by: Rodrigo Martínez Martínez

Major: Ingeniería en Cibernética (8vo Semestre)

Institution: Universidad Marista de Guadalajara (UMG)
