# 📦 Bot de Gestión de Materiales — Zooy / Fibra a la Casa

Sistema automatizado en Telegram para la gestión, aprobación y generación de vales de salida de materiales de almacén. Integra almacenamiento en base de datos MySQL, generación de reportes en Excel y respaldo automático en Google Drive.

---

## 🚀 Características Principales

- **Menú interactivo en Telegram:** Selección de materiales por categorías y carrito de compras dinámico.
- **Flujo de aprobación:** Notificaciones automáticas a administradores con botones de aprobación y rechazo en tiempo real.
- **Generación de vales:** Creación automática de documentos Excel basándose en la plantilla oficial (`.xlsx`).
- **Respaldo en la nube:** Subida automática del vale generado a Google Drive.
- **Doble entrega:** El técnico recibe un enlace directo a Google Drive y el archivo Excel adjunto en el chat de Telegram.

---

## 🛠️ Requisitos Previos

- Python 3.10 o superior.
- Base de datos MySQL.
- Cuenta de Google Cloud Console con acceso a la API de Google Drive habilitada.
- Un Bot de Telegram registrado a través de [@BotFather](https://t.me/BotFather).

---

## ⚙️ Instalación y Configuración

### 1. Clonar el repositorio
```bash
git clone [https://github.com/TU_USUARIO/TU_REPOSITORIO.git](https://github.com/TU_USUARIO/TU_REPOSITORIO.git)
cd TU_REPOSITORIO


# En macOS/Linux:
python3 -m venv venv
source venv/bin/activate

# En Windows:
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt