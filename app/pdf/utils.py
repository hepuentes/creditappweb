from fpdf import FPDF
import os
from datetime import datetime
from app.models import Configuracion

class CreditAppPDF(FPDF):
    """Clase base para todos los PDFs de CreditApp con estilo unificado"""
    
    def __init__(self, orientation='P', unit='mm', format='A4'):
        super().__init__(orientation, unit, format)
        self.set_auto_page_break(True, margin=15)
        self.add_font('Roboto', '', os.path.join(os.path.dirname(__file__), 'fonts', 'Roboto-Regular.ttf'), uni=True)
        self.add_font('Roboto', 'B', os.path.join(os.path.dirname(__file__), 'fonts', 'Roboto-Bold.ttf'), uni=True)
        self.add_font('Roboto', 'I', os.path.join(os.path.dirname(__file__), 'fonts', 'Roboto-Italic.ttf'), uni=True)
        
        # Obtener configuración de la empresa
        try:
            self.config = Configuracion.query.first()
        except:
            # Si hay error, usar valores por defecto
            self.config = None
    
    def header(self):
        # Logo
        if self.config and self.config.logo and os.path.exists(os.path.join('app', 'static', 'uploads', self.config.logo)):
            logo_path = os.path.join('app', 'static', 'uploads', self.config.logo)
            self.image(logo_path, 10, 8, 30)
            start_x = 45
        else:
            # Si no hay logo, usar solo texto
            start_x = 10
        
        # Nombre de la empresa y dirección
        self.set_font('Roboto', 'B', 16)
        self.set_text_color(0, 51, 102)  # Azul corporativo
        
        if self.config:
            self.cell(0, 10, self.config.nombre_empresa, 0, 1, 'R')
        else:
            self.cell(0, 10, 'CreditApp', 0, 1, 'R')
        
        # Información de contacto
        self.set_font('Roboto', '', 9)
        self.set_text_color(100, 100, 100)  # Gris oscuro
        
        if self.config:
            if self.config.direccion:
                self.cell(0, 5, self.config.direccion, 0, 1, 'R')
            if self.config.telefono:
                self.cell(0, 5, f"Tel: {self.config.telefono}", 0, 1, 'R')
        
        # Línea horizontal
        self.set_draw_color(0, 51, 102)
        self.line(10, self.get_y() + 2, 200, self.get_y() + 2)
        self.ln(10)
    
    def footer(self):
        # Posicionarse a 1.5 cm del final
        self.set_y(-15)
        # Línea horizontal
        self.set_draw_color(0, 51, 102)
        self.line(10, self.get_y() - 2, 200, self.get_y() - 2)
        # Fecha y número de página
        self.set_font('Roboto', 'I', 8)
        self.set_text_color(128, 128, 128)
        self.cell(0, 10, f'Generado: {datetime.now().strftime("%d/%m/%Y %H:%M")}', 0, 0, 'L')
        self.cell(0, 10, f'Página {self.page_no()}/{{nb}}', 0, 0, 'R')
    
    def titulo(self, texto, bg_color=(0, 51, 102), text_color=(255, 255, 255)):
        self.set_fill_color(*bg_color)
        self.set_text_color(*text_color)
        self.set_font('Roboto', 'B', 14)
        self.cell(0, 10, texto, 0, 1, 'C', fill=True)
        self.ln(5)
    
    def seccion(self, texto):
        self.set_font('Roboto', 'B', 12)
        self.set_text_color(0, 51, 102)
        self.cell(0, 8, texto, 0, 1)
        self.ln(2)
    
    def campo(self, etiqueta, valor, ancho_etiqueta=40):
        self.set_font('Roboto', 'B', 10)
        self.set_text_color(80, 80, 80)
        self.cell(ancho_etiqueta, 8, etiqueta + ':', 0)
        
        self.set_font('Roboto', '', 10)
        self.set_text_color(0, 0, 0)
        self.cell(0, 8, str(valor), 0, 1)
    
    def tabla_inicio(self, headers, col_widths=None):
        if col_widths is None:
            # Calcular anchos iguales
            col_widths = [190 / len(headers)] * len(headers)
        
        # Fondo del encabezado
        self.set_fill_color(240, 240, 240)
        self.set_text_color(0, 0, 0)
        self.set_font('Roboto', 'B', 10)
        self.set_draw_color(200, 200, 200)
        
        # Imprimir encabezados
        for i, header in enumerate(headers):
            self.cell(col_widths[i], 7, header, 1, 0, 'C', fill=True)
        self.ln()
        
        # Configurar para filas de datos
        self.set_font('Roboto', '', 10)
        self.set_fill_color(255, 255, 255)
        
        return col_widths
    
    def tabla_fila(self, data, col_widths, fill=False):
        if fill:
            self.set_fill_color(245, 245, 245)
        else:
            self.set_fill_color(255, 255, 255)
        
        for i, item in enumerate(data):
            self.cell(col_widths[i], 6, str(item), 1, 0, 'L', fill)
        self.ln()
    
    def tabla_total(self, texto, valor, col_widths):
        ancho_total = sum(col_widths)
        ancho_texto = ancho_total * 0.8
        ancho_valor = ancho_total * 0.2
        
        self.set_font('Roboto', 'B', 10)
        self.set_fill_color(230, 230, 230)
        self.cell(ancho_texto, 7, texto, 1, 0, 'R', fill=True)
        self.cell(ancho_valor, 7, valor, 1, 1, 'R', fill=True)

    def formato_moneda(self, valor):
        """Formatea un valor numérico como moneda"""
        if self.config and self.config.moneda:
            moneda = self.config.moneda
        else:
            moneda = "$"
        
        return f"{moneda} {valor:,.0f}"
