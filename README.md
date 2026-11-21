# ☕ Cafetería UMG - Sistema de Gestión de Pedidos
> **Digitalizing the university snack bar experience with a Full-Stack approach.**

![React Native](https://img.shields.io/badge/React_Native-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![FastAPI](https://img.shields.io/badge/FastAPI-005571?style=for-the-badge&logo=fastapi)
![MySQL](https://img.shields.io/badge/MySQL-00000f?style=for-the-badge&logo=mysql&logoColor=white)
![Expo](https://img.shields.io/badge/Expo-000020?style=for-the-badge&logo=expo&logoColor=white)

---

## 🇪🇸 Resumen del Proyecto
Sistema Full-Stack para realizar y gestionar pedidos en la cafetería de la **Universidad Marista de Guadalajara (UMG)**. Incluye una aplicación para estudiantes (menú filtrado por **Comidas** y **Bebidas**, buscador, carrito y seguimiento en tiempo real de su orden) y un panel de administración/cocina para gestionar pedidos, catálogo desde Excel/CSV e historial de ventas.

### 🛠️ Arquitectura Técnica
- **Base de Datos:** MySQL / MariaDB (mediante XAMPP en entorno local) con pool de conexiones y transacciones.
- **Backend:** API REST + WebSockets construida con **FastAPI** (Python).
- **Frontend Estudiantes:** Aplicación móvil/web desarrollada en **React Native** con **Expo** y **Expo Router**.
- **Panel de Administración y Cocina (KDS):** Interfaz web servida en `/admin` con módulos en `admin_static/` protegidos por token de administrador.

---

## 🇺🇸 Project Overview
A Full-Stack ordering system for university students at Universidad Marista de Guadalajara. It provides menu browsing, category filtering (Food vs. Drinks), real-time order tracking, and an administrative dashboard for kitchen operations, catalog management (including Excel/CSV import), and sales history.

### 🌟 Key Features
- **Real-time order tracking** via WebSockets with automatic polling fallback.
- **Admin dashboard** with three views: **Cocina** (Kitchen), **Productos** (Catalog & Excel/CSV import), and **Historial** (Sales history & CSV export).
- **Price & catalog protection** keeping historical order prices intact and logging price changes.

---

## 🔐 Autenticación de Administrador (`ADMIN_TOKEN`)

Las rutas y vistas de administración y cocina (`/admin`, `/pedidos_activos`, cambios de estado y `/ws/cocina`) requieren una clave de administrador enviada mediante la cabecera `X-Admin-Token`.

- **Por defecto:** Si no defines la variable, el backend usa un valor por defecto (`umg-cocina`). **Cámbiala en tu entorno local/producción** antes de arrancar el servidor.
- **No subas claves reales al repositorio:** Configura siempre la clave en tu variable de entorno local.

```powershell
# PowerShell (sesión actual)
$env:ADMIN_TOKEN="tu-clave-de-administrador"

:: Windows CMD
set ADMIN_TOKEN=tu-clave-de-administrador