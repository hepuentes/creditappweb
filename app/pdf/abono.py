from app.pdf.utils import CreditAppPDF
from datetime import datetime

def generar_pdf_abono(abono):
    """Genera un PDF mejorado visualmente para un abono"""
    # Crear PDF
    pdf = CreditAppPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Título
    pdf.titulo("COMPROBANTE DE ABONO")
    
    # Información básica del abono
    pdf.seccion("INFORMACIÓN DEL ABONO")
    pdf.campo("Número de Recibo", f"{abono.id}")
    pdf.campo("Fecha", abono.fecha.strftime("%d/%m/%Y %H:%M"))
    pdf.campo("Cobrador", abono.cobrador.nombre)
    pdf.campo("Monto", pdf.formato_moneda(abono.monto))
    
    # Información del cliente
    pdf.ln(5)
    pdf.seccion("INFORMACIÓN DEL CLIENTE")
    pdf.campo("Cliente", abono.venta.cliente.nombre)
    pdf.campo("Documento", abono.venta.cliente.cedula)
    if abono.venta.cliente.telefono:
        pdf.campo("Teléfono", abono.venta.cliente.telefono)
    
    # Información de la venta
    pdf.ln(5)
    pdf.seccion("INFORMACIÓN DE LA VENTA")
    pdf.campo("Factura Nº", str(abono.venta_id))
    pdf.campo("Fecha de Venta", abono.venta.fecha.strftime("%d/%m/%Y"))
    pdf.campo("Valor Total", pdf.formato_moneda(abono.venta.total))
    pdf.campo("Saldo Anterior", pdf.formato_moneda(abono.venta.saldo_pendiente + abono.monto))
    pdf.campo("Abono Actual", pdf.formato_moneda(abono.monto))
    pdf.campo("Saldo Pendiente", pdf.formato_moneda(abono.venta.saldo_pendiente))
    
    # Si hay notas
    if abono.notas:
        pdf.ln(5)
        pdf.seccion("NOTAS")
        pdf.set_font('Roboto', '', 10)
        pdf.multi_cell(0, 5, abono.notas)
    
    # Firma
    pdf.ln(15)
    pdf.set_font('Roboto', '', 10)
    
    # Líneas para firmas
    pdf.line(30, pdf.get_y() + 20, 90, pdf.get_y() + 20)  # Línea para firma cliente
    pdf.line(120, pdf.get_y() + 20, 180, pdf.get_y() + 20)  # Línea para firma cobrador
    
    # Textos de firma
    pdf.set_xy(30, pdf.get_y() + 22)
    pdf.cell(60, 5, "Firma Cliente", 0, 0, 'C')
    
    pdf.set_xy(120, pdf.get_y())
    pdf.cell(60, 5, "Firma Cobrador", 0, 1, 'C')
    
    # Información legal
    pdf.ln(10)
    pdf.set_font('Roboto', 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5, "Este documento es un comprobante de pago válido generado por el sistema CreditApp.\nConserve este recibo como comprobante de su abono.")
    
    # Generar PDF en bytes
    pdf_bytes = pdf.output(dest='S')
    if isinstance(pdf_bytes, str):
        return pdf_bytes.encode('latin1')
    return bytes(pdf_bytes)
