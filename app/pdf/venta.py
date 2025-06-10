from app.pdf.utils import CreditAppPDF
from datetime import datetime

def generar_pdf_venta(venta):
    """Genera un PDF mejorado visualmente para una venta"""
    # Crear PDF
    pdf = CreditAppPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Título
    pdf.titulo("FACTURA DE VENTA")
    
    # Información básica de la venta
    pdf.seccion("INFORMACIÓN DE LA VENTA")
    pdf.campo("Número de Factura", f"{venta.id}")
    pdf.campo("Fecha", venta.fecha.strftime("%d/%m/%Y %H:%M"))
    pdf.campo("Tipo", "CONTADO" if venta.tipo == 'contado' else "CRÉDITO")
    pdf.campo("Estado", "PAGADO" if venta.estado == 'pagado' else "PENDIENTE")
    
    # Información del cliente
    pdf.ln(5)
    pdf.seccion("INFORMACIÓN DEL CLIENTE")
    pdf.campo("Cliente", venta.cliente.nombre)
    pdf.campo("Documento", venta.cliente.cedula)
    if venta.cliente.telefono:
        pdf.campo("Teléfono", venta.cliente.telefono)
    if venta.cliente.direccion:
        pdf.campo("Dirección", venta.cliente.direccion)
    
    # Detalles de productos
    pdf.ln(5)
    pdf.seccion("DETALLE DE PRODUCTOS")
    
    # Encabezados de la tabla
    headers = ["Cantidad", "Producto", "Precio Unit.", "Subtotal"]
    col_widths = pdf.tabla_inicio(headers, [20, 100, 35, 35])
    
    # Filas de productos
    fill = False
    for detalle in venta.detalles:
        datos = [
            str(detalle.cantidad),
            detalle.producto.nombre,
            pdf.formato_moneda(detalle.precio_unitario),
            pdf.formato_moneda(detalle.subtotal)
        ]
        pdf.tabla_fila(datos, col_widths, fill)
        fill = not fill  # Alternar colores
    
    # Totales
    pdf.tabla_total("TOTAL", pdf.formato_moneda(venta.total), col_widths)
    
    # Si es venta a crédito, agregar información de crédito
    if venta.tipo == 'credito':
        pdf.ln(10)
        pdf.seccion("INFORMACIÓN DE PAGO")
        pdf.campo("Saldo Pendiente", pdf.formato_moneda(venta.saldo_pendiente))
        
        if venta.abonos and len(venta.abonos) > 0:
            pdf.ln(5)
            pdf.seccion("ABONOS REALIZADOS")
            
            # Tabla de abonos
            headers = ["Fecha", "Monto", "Cobrador"]
            col_widths = pdf.tabla_inicio(headers, [60, 60, 70])
            
            fill = False
            for abono in venta.abonos:
                datos = [
                    abono.fecha.strftime("%d/%m/%Y"),
                    pdf.formato_moneda(abono.monto),
                    abono.cobrador.nombre
                ]
                pdf.tabla_fila(datos, col_widths, fill)
                fill = not fill
    
    # Agregar un código QR o información adicional
    pdf.ln(10)
    pdf.set_font('Roboto', 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5, "Este documento es un comprobante de venta generado por el sistema CreditApp.\nPara validar este documento, comuníquese con nosotros.")
    
    # Generar PDF en bytes
    pdf_bytes = pdf.output(dest='S')
    if isinstance(pdf_bytes, str):
        return pdf_bytes.encode('latin1')
    return bytes(pdf_bytes)
