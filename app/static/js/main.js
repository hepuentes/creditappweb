// main.js
document.addEventListener('DOMContentLoaded', () => {
  const sidebar = document.getElementById('sidebar');
  const content = document.getElementById('content');
  const sidebarToggleBtn = document.getElementById('sidebarCollapseContent');
  const sidebarToggleDesktop = document.getElementById('sidebarCollapseDesktop');
  
  // Función para cerrar sidebar en móvil
  function closeSidebar() {
    if (sidebar) {
      sidebar.classList.remove('show');
      document.body.classList.remove('sidebar-open');
    }
  }
  
  // Función para abrir sidebar en móvil
  function openSidebar() {
    if (sidebar) {
      sidebar.classList.add('show');
      document.body.classList.add('sidebar-open');
    }
  }
  
  // Función para toggle sidebar en móvil
  function toggleSidebar() {
    if (sidebar) {
      if (sidebar.classList.contains('show')) {
        closeSidebar();
      } else {
        openSidebar();
      }
    }
  }
  
  // Función para toggle sidebar en desktop - CORREGIDO
  function toggleSidebarDesktop() {
    if (sidebar && content) {
      sidebar.classList.toggle('collapsed');
      
      // Aplicar cambios al contenido usando CSS
      if (sidebar.classList.contains('collapsed')) {
        content.style.width = `calc(100% - ${getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width-collapsed')})`;
        content.style.marginLeft = getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width-collapsed');
        localStorage.setItem('sidebarState', 'collapsed');
      } else {
        content.style.width = `calc(100% - ${getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width')})`;
        content.style.marginLeft = getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width');
        localStorage.setItem('sidebarState', 'expanded');
      }
    }
  }
  
  // Event listener para el botón hamburguesa en móvil
  if (sidebarToggleBtn) {
    sidebarToggleBtn.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      toggleSidebar();
    });
  }
  
  // Event listener para el botón toggle en desktop
  if (sidebarToggleDesktop) {
    sidebarToggleDesktop.addEventListener('click', function(e) {
      e.preventDefault();
      e.stopPropagation();
      toggleSidebarDesktop();
    });
  }
  
  // Cerrar sidebar al hacer clic fuera en móvil
  document.addEventListener('click', function(e) {
    if (window.innerWidth < 768 && sidebar && sidebar.classList.contains('show')) {
      // Si el clic no es en el sidebar ni en el botón toggle
      if (!sidebar.contains(e.target) && !e.target.closest('#sidebarCollapseContent')) {
        closeSidebar();
      }
    }
  });
  
  // Cerrar sidebar al hacer clic en enlaces del menú en móvil
  const sidebarLinks = document.querySelectorAll('#sidebar a');
  sidebarLinks.forEach(link => {
    link.addEventListener('click', function() {
      if (window.innerWidth < 768) {
        // Pequeño delay para permitir la navegación
        setTimeout(() => {
          closeSidebar();
        }, 100);
      }
    });
  });
  
  // Manejar cambios de tamaño de ventana
  window.addEventListener('resize', () => {
    if (window.innerWidth >= 768) {
      // En pantallas grandes, restaurar el estado del sidebar
      closeSidebar(); // Remover clases de móvil
      
      // Aplicar estado guardado del sidebar en desktop
      const savedState = localStorage.getItem('sidebarState');
      if (savedState === 'collapsed') {
        sidebar.classList.add('collapsed');
        if (content) {
          content.style.width = `calc(100% - ${getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width-collapsed')})`;
          content.style.marginLeft = getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width-collapsed');
        }
      } else {
        sidebar.classList.remove('collapsed');
        if (content) {
          content.style.width = `calc(100% - ${getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width')})`;
          content.style.marginLeft = getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width');
        }
      }
    } else {
      // En móvil, resetear estilos inline y asegurar que sidebar esté oculto
      if (content) {
        content.style.width = '';
        content.style.marginLeft = '';
      }
      if (!sidebar.classList.contains('show')) {
        closeSidebar();
      }
    }
  });
  
  // Recuperar estado del sidebar desde localStorage (solo en desktop)
  if (window.innerWidth >= 768) {
    const savedState = localStorage.getItem('sidebarState');
    if (savedState === 'collapsed') {
      sidebar.classList.add('collapsed');
      if (content) {
        content.style.width = `calc(100% - ${getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width-collapsed')})`;
        content.style.marginLeft = getComputedStyle(document.documentElement).getPropertyValue('--sidebar-width-collapsed');
      }
    }
  }
  
  // Inicializar estado correcto al cargar
  if (window.innerWidth < 768) {
    closeSidebar();
    if (content) {
      content.style.width = '';
      content.style.marginLeft = '';
    }
  }
  
  // Auto-close alerts después de 5 segundos
  setTimeout(function() {
    const alerts = document.querySelectorAll('.alert');
    alerts.forEach(alert => {
      if (bootstrap && bootstrap.Alert) {
        const bsAlert = new bootstrap.Alert(alert);
        bsAlert.close();
      } else {
        alert.classList.add('fade');
        setTimeout(() => {
          alert.remove();
        }, 300);
      }
    });
  }, 5000);
  
  // Inicializar tooltips
  const tooltipTriggerList = document.querySelectorAll('[data-bs-toggle="tooltip"]');
  if (tooltipTriggerList.length > 0 && bootstrap && bootstrap.Tooltip) {
    [...tooltipTriggerList].map(tooltipTriggerEl => new bootstrap.Tooltip(tooltipTriggerEl));
  }

  // Función para actualizar total de venta
  window.actualizarTotal = function() {
    const subtotales = document.querySelectorAll('#tabla-productos .subtotal');
    let suma = 0;
    
    subtotales.forEach(subtotal => {
      suma += parseFloat(subtotal.textContent.replace(/[^\d.-]/g, '')) || 0;
    });
    
    const totalVenta = document.getElementById('total-venta');
    if (totalVenta) {
      totalVenta.textContent = new Intl.NumberFormat('es-CO', {
        style: 'currency',
        currency: 'COP',
        minimumFractionDigits: 0
      }).format(suma);
    }
  };
});
