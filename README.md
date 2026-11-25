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
```bash
# Navegar a la carpeta / Navigate to folder
cd backend_api    

# Activar entorno virtual / Activate venv
.\.venv\Scripts\activate

# Instalar dependencias (incluye 'websockets' para el tiempo real)
pip install -r requirements.txt

# Iniciar servidor / Start Server
python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000