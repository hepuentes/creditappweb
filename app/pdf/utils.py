from fpdf import FPDF
import os
from datetime import datetime
from app.models import Configuracion


class CreditAppPDF(FPDF):
    """Clase base para todos los PDFs de CreditApp con estilo unificado"""

    def __init__(self, orientation="P", unit="mm", format="A4"):
        super().__init__(orientation, unit, format)
        self.set_auto_page_break(True, margin=15)
        self.add_font(
            "Roboto",
            "",
            os.path.join(os.path.dirname(__file__), "fonts", "Roboto-Regular.ttf"),
            uni=True,
        )
        self.add_font(
            "Roboto",
            "B",
            os.path.join(os.path.dirname(__file__), "fonts", "Roboto-Bold.ttf"),
            uni=True,
        )
        self.add_font(
            "Roboto",
            "I",
            os.path.join(os.path.dirname(__file__), "fonts", "Roboto-Italic.ttf"),
            uni=True,
        )

        try:
            self.config = Configuracion.query.first()
        except:
            self.config = None

    def header(self):
        text_y = 10

        # Texto "CreditApp" como logo
        self.set_xy(10, text_y)
        self.set_font("Roboto", "B", 16)
        self.set_text_color(30, 100, 200)
        self.cell(self.get_string_width("Credit"), 8, "Credit", 0, 0, "L")
        self.set_text_color(50, 180, 90)
        self.cell(self.get_string_width("App"), 8, "App", 0, 0, "L")

        # Info contacto alineada a la derecha
        self.set_text_color(100, 100, 100)
        self.set_font("Roboto", "", 9)
        direccion = (
            self.config.direccion if self.config and self.config.direccion else ""
        )
        telefono = self.config.telefono if self.config and self.config.telefono else ""
        contacto = ""
        if direccion and telefono:
            contacto = f"{direccion}   |   Tel: {telefono}"
        elif direccion:
            contacto = direccion
        elif telefono:
            contacto = f"Tel: {telefono}"
        self.set_xy(45, text_y + 2)
        self.cell(0, 6, contacto, 0, 1, "R")

        # Línea horizontal debajo del logo/texto e info contacto
        self.set_draw_color(0, 51, 102)
        self.set_y(text_y + 12)
        self.line(10, self.get_y(), 200, self.get_y())
        self.ln(3)

    def footer(self):
        self.set_y(-15)
        self.set_draw_color(0, 51, 102)
        self.line(10, self.get_y() - 2, 200, self.get_y() - 2)
        self.set_font("Roboto", "I", 8)
        self.set_text_color(100, 100, 100)
        self.set_x(10)
        self.cell(
            0,
            6,
            "Este documento es un comprobante de venta por el sistema CreditApp. Para validar este documento, comuníquese con nosotros.",
            0,
            0,
            "L",
        )

    def titulo(self, texto, bg_color=(0, 51, 102), text_color=(255, 255, 255)):
        self.set_fill_color(*bg_color)
        self.set_text_color(*text_color)
        self.set_font("Roboto", "B", 14)
        self.cell(0, 8, texto, 0, 1, "C", fill=True)
        self.ln(3)

    def seccion(self, texto):
        self.set_font("Roboto", "B", 11)
        self.set_text_color(0, 51, 102)
        self.cell(0, 6, texto, 0, 1)
        self.ln(1)

    def campo(self, etiqueta, valor, ancho_etiqueta=40):
        self.set_font("Roboto", "B", 10)
        self.set_text_color(80, 80, 80)
        self.cell(ancho_etiqueta, 6, etiqueta + ":", 0)

        self.set_font("Roboto", "", 10)
        self.set_text_color(0, 0, 0)
        self.cell(0, 6, str(valor), 0, 1)

    def tabla_inicio(self, headers, col_widths=None):
        if col_widths is None:
            col_widths = [190 / len(headers)] * len(headers)

        self.set_fill_color(240, 240, 240)
        self.set_text_color(0, 0, 0)
        self.set_font("Roboto", "B", 10)
        self.set_draw_color(200, 200, 200)

        for i, header in enumerate(headers):
            self.cell(col_widths[i], 8, header, 1, 0, "C", fill=True)
        self.ln()

        self.set_font("Roboto", "", 10)
        self.set_fill_color(255, 255, 255)

        return col_widths

    def tabla_fila(self, data, col_widths, fill=False, centrar_columnas=None):
        if fill:
            self.set_fill_color(245, 245, 245)
        else:
            self.set_fill_color(255, 255, 255)

        if centrar_columnas is None:
            centrar_columnas = []

        for i, item in enumerate(data):
            align = "C" if i in centrar_columnas else "L"
            self.cell(col_widths[i], 7, str(item), 1, 0, align, fill)
        self.ln()

    def tabla_total(self, texto, valor, col_widths):
        self.set_font("Roboto", "B", 10)
        self.set_fill_color(230, 230, 230)

        ancho_texto = sum(col_widths[:-1])
        ancho_valor = col_widths[-1]

        self.cell(ancho_texto, 8, texto, 1, 0, "C", fill=True)
        self.cell(ancho_valor, 8, valor, 1, 1, "C", fill=True)

    def formato_moneda(self, valor):
        if self.config and self.config.moneda:
            moneda = self.config.moneda
        else:
            moneda = "$"
        return f"{moneda} {valor:,.0f}"
