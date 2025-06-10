# CreditApp - Sistema de Gestión de Créditos

CreditApp es un sistema completo de gestión de ventas, inventario y créditos desarrollado con Flask (Python) para pequeñas y medianas empresas. Permite administrar clientes, productos, ventas, créditos, abonos y cajas en una interfaz sencilla y amigable.

## Características Principales

- **Autenticación y Roles**: Niveles de acceso diferenciados para administradores, vendedores y cobradores.
- **Dashboard**: Resumen visual de la actividad del negocio.
- **Gestión de Clientes**: Registro completo de clientes con historial de compras y créditos.
- **Inventario**: Control de productos con alertas de stock bajo.
- **Ventas**: Registro de ventas al contado y a crédito.
- **Créditos y Abonos**: Seguimiento de créditos y registro de pagos parciales.
- **Cajas**: Control de diferentes formas de pago (efectivo, Nequi, Daviplata, etc.).
- **Comisiones**: Cálculo automático de comisiones por ventas y abonos.
- **Reportes**: Exportación en CSV.
- **Facturas**: Generación de PDFs para ventas y abonos, con opción de compartir por WhatsApp.

## Requisitos del Sistema

- Python 3.8 o superior
- PostgreSQL (recomendado para producción) o SQLite (para desarrollo)
- Bibliotecas Python detalladas en requirements.txt

## Instalación

1. **Clonar el repositorio**:

## Despliegue en Railway

En la sección **Variables** de tu proyecto en Railway define:

1. `DATABASE_URL`: la cadena de conexión de PostgreSQL proporcionada por Railway.
2. `SECRET_KEY`: una cadena aleatoria para la configuración de Flask.

Guarda los cambios y vuelve a desplegar la aplicación.
