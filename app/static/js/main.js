/* Global Styles */
:root {
  --primary-color: #007bff;
  --secondary-color: #6c757d;
  --success-color: #28a745;
  --danger-color: #dc3545;
  --warning-color: #ffc107;
  --info-color: #17a2b8;
  --light-color: #f8f9fa;
  --dark-color: #343a40;
  --sidebar-width: 280px;
  --sidebar-width-collapsed: 60px;
  --header-height: 60px;
  --transition-speed: 0.3s;
}

body {
  font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
  background-color: #f5f5f5;
  min-height: 100vh;
  display: flex;
  flex-direction: column;
  position: relative;
  overflow-x: hidden;
}

.wrapper {
  display: flex;
  align-items: stretch;
  flex-grow: 1;
}

/* Sidebar Styles */
.sidebar {
  min-width: var(--sidebar-width);
  max-width: var(--sidebar-width);
  background: #343a40;
  color: #fff;
  transition: all var(--transition-speed) ease;
  height: 100vh;
  position: fixed;
  top: 0;
  left: 0;
  z-index: 1050;
  overflow-y: auto;
  box-shadow: 2px 0 5px rgba(0, 0, 0, 0.1);
}

/* Sidebar Collapsed State */
.sidebar.collapsed {
  min-width: var(--sidebar-width-collapsed);
  max-width: var(--sidebar-width-collapsed);
}

.sidebar.collapsed .sidebar-header h3 {
  display: none;
}

.sidebar.collapsed ul li a span {
  display: none;
}

.sidebar.collapsed ul li a {
  text-align: center;
  padding: 15px 0;
}

.sidebar.collapsed ul li a i {
  font-size: 1.5rem;
  margin-right: 0;
  display: block;
  width: 100%;
  text-align: center;
}

.sidebar.collapsed ul ul a {
  padding-left: 0 !important;
}

.sidebar .sidebar-header {
  padding: 15px 20px;
  background: #212529;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #495057;
}

.sidebar .sidebar-header h3 {
  color: #fff;
  margin-bottom: 0;
  font-size: 1.5rem;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* Enlaces del Sidebar */
.sidebar ul.components {
  padding: 15px 0;
}

.sidebar ul li a {
  padding: 12px 20px;
  font-size: 0.95em;
  display: block;
  color: #adb5bd;
  text-decoration: none;
  transition: all var(--transition-speed) ease;
  border-left: 3px solid transparent;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.sidebar ul li a:hover {
  color: #fff;
  background: var(--primary-color);
  border-left-color: #fff;
}

.sidebar ul li.active>a {
  color: #fff;
  background: var(--primary-color);
  border-left-color: #fff;
}

.sidebar ul li a i {
  margin-right: 12px;
  width: 20px;
  text-align: center;
  transition: all var(--transition-speed) ease;
}

.sidebar ul ul a {
  padding-left: 45px !important;
  background: #2c3136;
  font-size: 0.9em;
}

/* Content Styles */
#content {
  width: calc(100% - var(--sidebar-width));
  margin-left: var(--sidebar-width);
  padding: 0;
  min-height: 100vh;
  transition: all var(--transition-speed) ease;
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  position: relative;
}

/* Content with collapsed sidebar */
.sidebar.collapsed~#content {
  width: calc(100% - var(--sidebar-width-collapsed));
  margin-left: var(--sidebar-width-collapsed);
}

/* Alternativa usando clase en body si es necesario */
body.sidebar-collapsed #content {
  width: calc(100% - var(--sidebar-width-collapsed));
  margin-left: var(--sidebar-width-collapsed);
}

/* Navbar Principal */
#content>.navbar {
  padding: 10px 20px;
  background-color: #fff;
  border-bottom: 1px solid #dee2e6;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
  min-height: var(--header-height);
  display: flex;
  align-items: center;
  position: sticky;
  top: 0;
  z-index: 1030;
}

/* BOTÓN HAMBURGUESA MÓVIL - SIEMPRE VISIBLE EN MÓVIL */
.mobile-toggle-btn {
  background: var(--primary-color);
  border: none;
  color: white;
  padding: 8px 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: all var(--transition-speed) ease;
  display: none;
  font-size: 1.2rem;
}

.mobile-toggle-btn:hover {
  background: #0056b3;
}

/* Botón toggle sidebar en desktop */
.sidebar-toggle-btn {
  background: transparent;
  border: none;
  color: white;
  padding: 8px 12px;
  border-radius: 4px;
  cursor: pointer;
  transition: all var(--transition-speed) ease;
}

.sidebar-toggle-btn:hover {
  background: rgba(255, 255, 255, 0.1);
  color: var(--primary-color);
}

/* Perfil de usuario mejorado */
.user-profile-dropdown {
  position: relative;
}

.user-profile-link {
  text-decoration: none;
  color: var(--dark-color);
  display: flex;
  align-items: center;
  padding: 0.5rem;
  border-radius: 0.25rem;
  transition: all 0.2s ease;
}

.user-profile-link:hover {
  background-color: rgba(0, 0, 0, 0.05);
  color: var(--dark-color);
}

.avatar-circle {
  width: 35px;
  height: 35px;
  background-color: var(--primary-color);
  border-radius: 50%;
  display: flex;
  justify-content: center;
  align-items: center;
  color: white;
  font-weight: bold;
}

.initials {
  font-size: 1.2rem;
}

.user-info {
  line-height: 1.2;
}

.user-name {
  font-weight: 600;
  font-size: 0.95rem;
}

.user-role {
  font-size: 0.8rem;
  color: var(--secondary-color);
}

/* RESPONSIVE STYLES CORREGIDOS */
@media (max-width: 767.98px) {

  /* MOSTRAR BOTÓN HAMBURGUESA EN MÓVIL */
  .mobile-toggle-btn {
     display: block !important;
  }

  /* En móvil, sidebar oculto por defecto */
  .sidebar {
     margin-left: calc(-1 * var(--sidebar-width));
     transition: margin-left var(--transition-speed) ease;
     z-index: 1060;
  }

  /* Cuando sidebar está activo (visible) en móvil */
  .sidebar.show {
     margin-left: 0;
  }

  /* Content ocupa todo el ancho en móvil */
  #content {
     width: 100% !important;
     margin-left: 0 !important;
  }

  /* Overlay cuando sidebar está abierto en móvil */
  body.sidebar-open .sidebar-overlay {
     display: block !important;
  }

  /* Ajustes para el header en móvil - MANTENER CREDITAPP VISIBLE */
  .sidebar-header {
     justify-content: space-between;
     padding: 15px;
  }

  .sidebar-header h3 {
     display: block !important;
     font-size: 1.2rem !important;
     opacity: 1 !important;
  }

  .sidebar-toggle-btn {
     margin: 0;
  }

  /* Ajustes de padding para móvil */
  .container-fluid {
     padding-left: 15px;
     padding-right: 15px;
  }
}

/* Para tablets y pantallas medianas */
@media (min-width: 768px) and (max-width: 991.98px) {
  :root {
     --sidebar-width: 220px;
     --sidebar-width-collapsed: 60px;
  }

  .sidebar ul li a {
     padding: 10px 15px;
     font-size: 0.9em;
  }
}

/* Dashboard Cards Responsive */
.card-dashboard-container {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(250px, 1fr));
  gap: 1rem;
  width: 100%;
}

.card-dashboard {
  text-align: center;
  min-height: 160px;
  display: flex;
  flex-direction: column;
  height: 100%;
}

.card-dashboard .card-body {
  flex-grow: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.card-dashboard .card-value {
  font-size: 2.5rem;
  font-weight: 700;
  margin-bottom: 0;
}

.card-dashboard .card-label {
  font-size: 1rem;
  color: #6c757d;
}

.card-dashboard .card-icon {
  font-size: 1.8rem;
  margin-bottom: 10px;
}

/* Resto del CSS original */
.card {
  margin-bottom: 20px;
  border: none;
  border-radius: 8px;
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  transition: transform 0.2s ease;
}

.card:hover {
  transform: translateY(-3px);
}

.card-header {
  font-weight: 600;
  background-color: #f8f9fa;
  border-bottom: 1px solid #e9ecef;
}

/* Buttons and Forms */
.btn-primary {
  background-color: var(--primary-color);
  border-color: var(--primary-color);
}

.btn-primary:hover {
  background-color: #0069d9;
  border-color: #0062cc;
}

/* Tables */
.table-responsive {
  box-shadow: 0 2px 10px rgba(0, 0, 0, 0.1);
  border-radius: 8px;
  overflow: hidden;
}

.table {
  margin-bottom: 0;
}

.table thead th {
  background-color: #f8f9fa;
  border-bottom: 2px solid #dee2e6;
}

.table-hover tbody tr:hover {
  background-color: rgba(0, 123, 255, 0.05);
}

/* Footer */
.footer {
  margin-top: auto;
  background-color: #e9ecef;
  border-top: 1px solid #dee2e6;
  padding: 15px 0;
}

/* Login page styles */
.login-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: #f5f5f5;
}

.login-form {
  max-width: 400px;
  width: 100%;
  padding: 30px;
  border-radius: 10px;
  background-color: #fff;
  box-shadow: 0 4px 20px rgba(0, 0, 0, 0.1);
}

.login-form .card-header {
  text-align: center;
  font-size: 24px;
  font-weight: 600;
  margin-bottom: 20px;
  border-bottom: none;
  background-color: transparent;
}

.login-logo {
  text-align: center;
  margin-bottom: 25px;
}

.login-logo img {
  max-width: 150px;
}

/* Botones en pantallas pequeñas */
@media (max-width: 767.98px) {

  /* Botones de acción más compactos */
  .btn-group .btn {
     padding: 0.25rem 0.4rem;
     font-size: 0.8rem;
  }

  .btn-group .btn i {
     font-size: 0.9rem;
  }

  /* Cards del dashboard más compactas */
  .card-dashboard .card-value {
     font-size: 1.8rem;
  }

  .card-dashboard .card-label {
     font-size: 0.85rem;
  }

  .card-dashboard .card-icon {
     font-size: 1.4rem;
  }

  /* Tablas responsive mejoradas */
  .table-responsive {
     font-size: 0.85rem;
  }

  .table th,
  .table td {
     padding: 0.5rem 0.25rem;
     white-space: nowrap;
     overflow: hidden;
     text-overflow: ellipsis;
     max-width: 120px;
  }

  /* Formularios más compactos */
  .form-control,
  .form-select {
     font-size: 0.9rem;
     padding: 0.5rem 0.75rem;
  }

  .form-label {
     font-size: 0.9rem;
     margin-bottom: 0.25rem;
  }

  /* Headers más compactos */
  h1 {
     font-size: 1.5rem;
  }

  h5,
  .h5 {
     font-size: 1.1rem;
  }

  /* Espaciado reducido */
  .mb-4 {
     margin-bottom: 1.5rem !important;
  }

  .mb-3 {
     margin-bottom: 1rem !important;
  }

  /* Cards más compactas */
  .card-body {
     padding: 1rem;
  }

  .card-header {
     padding: 0.75rem 1rem;
     font-size: 0.95rem;
  }

  /* Modales más compactos */
  .modal-dialog {
     margin: 0.5rem;
  }

  .modal-body {
     padding: 1rem;
  }

  /* Badges más pequeños */
  .badge {
     font-size: 0.7rem;
     padding: 0.25em 0.4em;
  }

  /* Alertas más compactas */
  .alert {
     padding: 0.5rem 0.75rem;
     font-size: 0.85rem;
  }

  /* Navegación usuario más compacta */
  .user-info {
     display: none !important;
  }

  .avatar-circle {
     width: 30px;
     height: 30px;
  }

  .initials {
     font-size: 1rem;
  }
}

/* Para tablets (768px - 991px) */
@media (min-width: 768px) and (max-width: 991.98px) {

  .table th,
  .table td {
     padding: 0.6rem 0.4rem;
     font-size: 0.9rem;
  }

  .btn-group .btn {
     padding: 0.3rem 0.5rem;
     font-size: 0.85rem;
  }

  .card-dashboard .card-value {
     font-size: 2.2rem;
  }
}

/* Mejoras para elementos específicos */
.container-fluid {
  padding-left: 10px;
  padding-right: 10px;
}

@media (min-width: 768px) {
  .container-fluid {
     padding-left: 15px;
     padding-right: 15px;
  }
}

/* Botones responsive mejorados */
.btn-responsive {
  padding: 0.375rem 0.75rem;
  font-size: 0.875rem;
}

@media (max-width: 767.98px) {
  .btn-responsive {
     padding: 0.25rem 0.5rem;
     font-size: 0.8rem;
  }

  .btn-responsive i {
     font-size: 0.9rem;
  }
}

/* Texto truncado en pantallas pequeñas */
@media (max-width: 767.98px) {
  .text-truncate-mobile {
     white-space: nowrap;
     overflow: hidden;
     text-overflow: ellipsis;
     max-width: 100px;
  }
}

/* Clases de utilidad */
.form-text {
  font-size: 0.85rem;
}

.form-control.is-invalid,
.form-select.is-invalid {
  background-position: right calc(0.375em + 0.55rem) center;
}

.numeric-only::-webkit-inner-spin-button,
.numeric-only::-webkit-outer-spin-button {
  -webkit-appearance: none;
  margin: 0;
}

.numeric-only {
  -moz-appearance: textfield;
}

.btn-group .btn-sm {
  padding: 0.25rem 0.5rem;
  font-size: 0.75rem;
}

.container-fluid {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
}

.table-responsive {
  overflow-x: auto;
  width: 100%;
}

.table th,
.table td {
  white-space: normal;
  vertical-align: middle;
}

.row {
  width: 100%;
  margin-left: 0;
  margin-right: 0;
}

/* ========================================
 OPTIMIZACIONES PARA GESTIÓN DE COBROS
 ======================================== */

/* Contenedor principal responsivo */
.container-fluid {
  padding-left: 10px;
  padding-right: 10px;
}

/* Tarjetas de resumen para móvil */
@media (max-width: 768px) {
  .resumen-tabs {
     flex-direction: column;
     gap: 10px;
  }

  .resumen-card {
     padding: 15px;
     margin-bottom: 10px;
     min-width: 100%;
     text-align: center;
  }

  .resumen-numero {
     font-size: 1.8rem !important;
     font-weight: bold;
  }

  .resumen-monto {
     color: #28a745 !important;
  }

  .resumen-label {
     font-size: 0.9rem;
     color: #6c757d;
     margin-top: 5px;
  }
}

/* Pestañas de cobros optimizadas para móvil */
.nav-tabs-cobros {
  border-bottom: 2px solid #dee2e6;
  margin-bottom: 20px;
  overflow-x: auto;
  white-space: nowrap;
  scrollbar-width: none;
  -ms-overflow-style: none;
}

.nav-tabs-cobros::-webkit-scrollbar {
  display: none;
}

@media (max-width: 768px) {
  .nav-tabs-cobros .nav-item {
     min-width: 120px;
     text-align: center;
  }

  .nav-tabs-cobros .nav-link {
     padding: 10px 8px;
     font-size: 0.9rem;
     display: flex;
     flex-direction: column;
     align-items: center;
     border-radius: 8px 8px 0 0;
  }

  .nav-tabs-cobros .badge {
     margin-top: 2px !important;
     margin-left: 0 !important;
     font-size: 0.75rem;
     padding: 2px 6px;
  }
}

/* Tarjetas de cobro para móvil */
.cobro-card {
  background: white;
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 12px;
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  border-left: 4px solid #007bff;
  transition: all 0.3s ease;
}

.cobro-card.vencida {
  border-left-color: #dc3545;
  background: linear-gradient(135deg, #fff5f5 0%, #ffffff 100%);
}

.cobro-card.para-hoy {
  border-left-color: #ffc107;
  background: linear-gradient(135deg, #fffbf0 0%, #ffffff 100%);
}

.cobro-card.proxima {
  border-left-color: #17a2b8;
  background: linear-gradient(135deg, #f0fbff 0%, #ffffff 100%);
}

@media (max-width: 768px) {
  .cobro-card {
     padding: 12px;
     margin-bottom: 10px;
  }

  .cobro-header {
     display: flex;
     justify-content: space-between;
     align-items: flex-start;
     margin-bottom: 10px;
  }

  .cliente-info h6 {
     font-size: 1.1rem;
     margin-bottom: 2px;
     color: #2c3e50;
     font-weight: 600;
  }

  .cliente-telefono {
     font-size: 0.85rem;
     color: #6c757d;
     display: flex;
     align-items: center;
     gap: 4px;
  }

  .monto-cuota {
     font-size: 1.3rem;
     font-weight: bold;
     color: #e74c3c;
  }

  .monto-cuota.para-hoy {
     color: #f39c12;
  }

  .monto-cuota.proxima {
     color: #3498db;
  }
}

/* Información de vencimiento móvil */
.vencimiento-info {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 8px 0;
  border-top: 1px solid #f8f9fa;
  margin-top: 10px;
}

@media (max-width: 768px) {
  .vencimiento-info {
     flex-direction: column;
     align-items: stretch;
     gap: 8px;
  }

  .fecha-vencimiento {
     font-size: 0.85rem;
     color: #495057;
     display: flex;
     align-items: center;
     justify-content: center;
     gap: 4px;
  }

  .dias-atraso {
     background: #dc3545;
     color: white;
     padding: 2px 8px;
     border-radius: 12px;
     font-size: 0.75rem;
     font-weight: 500;
     text-align: center;
  }

  .dias-proximos {
     background: #17a2b8;
     color: white;
     padding: 2px 8px;
     border-radius: 12px;
     font-size: 0.75rem;
     font-weight: 500;
     text-align: center;
  }
}

/* Botones de acción para móvil */
.acciones-cobro {
  display: flex;
  gap: 8px;
  margin-top: 12px;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .acciones-cobro .btn {
     flex: 1;
     min-width: 0;
     padding: 8px 12px;
     font-size: 0.85rem;
     border-radius: 8px;
     display: flex;
     align-items: center;
     justify-content: center;
     gap: 4px;
  }

  .btn-whatsapp {
     background: #25d366;
     border-color: #25d366;
     color: white;
  }

  .btn-abonar {
     background: #007bff;
     border-color: #007bff;
     color: white;
  }

  .btn-detalle {
     background: #6c757d;
     border-color: #6c757d;
     color: white;
  }
}

/* Estados vacíos optimizados */
.estado-vacio {
  text-align: center;
  padding: 40px 20px;
  color: #6c757d;
}

@media (max-width: 768px) {
  .estado-vacio {
     padding: 30px 15px;
  }

  .estado-vacio i {
     font-size: 3rem;
     margin-bottom: 15px;
     opacity: 0.5;
  }

  .estado-vacio h5 {
     font-size: 1.2rem;
     margin-bottom: 8px;
     color: #495057;
  }

  .estado-vacio p {
     font-size: 0.9rem;
     line-height: 1.4;
     margin-bottom: 0;
  }
}

/* ========================================
OPTIMIZACIONES PARA TRANSFERENCIAS
======================================== */

/* Tabla de transferencias responsiva */
@media (max-width: 768px) {
  .table-responsive {
     border: none;
     margin-bottom: 0;
  }

  .table-mobile {
     display: none;
  }

  .card-mobile {
     display: block;
  }

  .transferencia-card {
     background: white;
     border-radius: 10px;
     padding: 15px;
     margin-bottom: 15px;
     box-shadow: 0 2px 8px rgba(0, 0, 0, 0.08);
     border: 1px solid #e9ecef;
  }

  .transferencia-header {
     display: flex;
     justify-content: space-between;
     align-items: flex-start;
     margin-bottom: 10px;
     padding-bottom: 8px;
     border-bottom: 1px solid #f8f9fa;
  }

  .venta-numero {
     font-weight: 600;
     color: #007bff;
     font-size: 1.1rem;
  }

  .transferencia-fecha {
     font-size: 0.8rem;
     color: #6c757d;
  }

  .transferencia-detalles {
     display: grid;
     grid-template-columns: 1fr 1fr;
     gap: 10px;
     margin-bottom: 10px;
  }

  .detalle-item {
     display: flex;
     flex-direction: column;
  }

  .detalle-label {
     font-size: 0.75rem;
     color: #6c757d;
     text-transform: uppercase;
     letter-spacing: 0.5px;
     margin-bottom: 2px;
  }

  .detalle-valor {
     font-size: 0.9rem;
     color: #495057;
     font-weight: 500;
  }
}

/* ========================================
COMPONENTES GENERALES MÓVIL
======================================== */

/* Header responsivo */
@media (max-width: 768px) {
  .page-header {
     padding: 15px 0;
  }

  .page-header .row {
     align-items: flex-start;
  }

  .page-header h1 {
     font-size: 1.5rem;
     margin-bottom: 8px;
  }

  .page-header p {
     font-size: 0.9rem;
     line-height: 1.4;
  }

  .header-actions {
     margin-top: 10px;
     text-align: right;
  }

  .btn-actualizar {
     padding: 8px 16px;
     font-size: 0.9rem;
     border-radius: 8px;
     background: #ffffff;
     border: 2px solid rgba(255, 255, 255, 0.3);
     color: #6f42c1;
     font-weight: 500;
  }
}

/* Navegación principal móvil */
@media (max-width: 768px) {
  .navbar-nav {
     padding: 10px 0;
  }

  .nav-link {
     padding: 12px 20px !important;
     border-bottom: 1px solid rgba(255, 255, 255, 0.1);
     display: flex;
     align-items: center;
     gap: 10px;
  }

  .nav-link i {
     width: 20px;
     text-align: center;
  }
}

/* Botones de acción flotantes para móvil */
@media (max-width: 768px) {
  .floating-actions {
     position: fixed;
     bottom: 20px;
     right: 20px;
     z-index: 1000;
     display: flex;
     flex-direction: column;
     gap: 10px;
  }

  .btn-floating {
     width: 56px;
     height: 56px;
     border-radius: 50%;
     display: flex;
     align-items: center;
     justify-content: center;
     box-shadow: 0 4px 16px rgba(0, 0, 0, 0.2);
     border: none;
     font-size: 1.2rem;
     transition: all 0.3s ease;
  }

  .btn-floating:hover {
     transform: scale(1.1);
     box-shadow: 0 6px 20px rgba(0, 0, 0, 0.3);
  }

  .btn-floating.btn-primary {
     background: linear-gradient(135deg, #007bff, #0056b3);
  }

  .btn-floating.btn-success {
     background: linear-gradient(135deg, #28a745, #1e7e34);
  }
}

/* Formularios optimizados para móvil */
@media (max-width: 768px) {
  .form-label {
     font-weight: 600;
     color: #495057;
     margin-bottom: 5px;
     font-size: 0.9rem;
  }

  .form-control,
  .form-select {
     padding: 12px 15px;
     border-radius: 8px;
     border: 2px solid #e9ecef;
     font-size: 1rem;
     transition: all 0.3s ease;
  }

  .form-control:focus,
  .form-select:focus {
     border-color: #007bff;
     box-shadow: 0 0 0 0.2rem rgba(0, 123, 255, 0.15);
  }

  .form-text {
     font-size: 0.8rem;
     margin-top: 4px;
     color: #6c757d;
  }
}

/* Alertas optimizadas */
@media (max-width: 768px) {
  .alert {
     border-radius: 8px;
     padding: 12px 15px;
     margin-bottom: 15px;
     border: none;
     box-shadow: 0 2px 8px rgba(0, 0, 0, 0.1);
  }

  .alert-dismissible .btn-close {
     padding: 8px 10px;
  }
}

/* Utilidades móviles */
@media (max-width: 768px) {
  .mobile-hidden {
     display: none !important;
  }

  .mobile-visible {
     display: block !important;
  }

  .mobile-center {
     text-align: center !important;
  }

  .mobile-full-width {
     width: 100% !important;
  }

  .mobile-no-margin {
     margin: 0 !important;
  }

  .mobile-small-text {
     font-size: 0.85rem !important;
  }

  .mobile-padding {
     padding: 10px !important;
  }
}