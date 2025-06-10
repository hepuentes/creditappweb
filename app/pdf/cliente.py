from app.pdf.utils import CreditAppPDF
from datetime import datetime

def generar_pdf_historial(cliente, ventas, creditos, abonos):
    """Genera un PDF mejorado visualmente para el historial de un cliente"""
    # Crear PDF
    pdf = CreditAppPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Título
    pdf.titulo(f"HISTORIAL DEL CLIENTE")
    
    # Información del cliente
    pdf.seccion("DATOS DEL CLIENTE")
    pdf.campo("Nombre", cliente.nombre)
    pdf.campo("Documento", cliente.cedula)
    if cliente.telefono:
        pdf.campo("Teléfono", cliente.telefono)
    if cliente.email:
        pdf.campo("Email", cliente.email)
    if cliente.direccion:
        pdf.campo("Dirección", cliente.direccion)
    pdf.campo("Fecha Registro", cliente.fecha_registro.strftime("%d/%m/%Y"))
    
    # Ventas realizadas
    if ventas:
        pdf.ln(10)
        pdf.seccion("VENTAS REALIZADAS")
        
        # Tabla de ventas
        headers = ["Fecha", "Factura", "Tipo", "Total", "Estado"]
        col_widths = pdf.tabla_inicio(headers, [40, 25, 30, 50, 45])
        
        fill = False
        for venta in sorted(ventas, key=lambda v: v.fecha, reverse=True):
            tipo = "CONTADO" if venta.tipo == 'contado' else "CRÉDITO"
            estado = "PAGADO" if venta.estado == 'pagado' else "PENDIENTE"
            
            datos = [
                venta.fecha.strftime("%d/%m/%Y"),
                f"#{venta.id}",
                tipo,
                pdf.formato_moneda(venta.total),
                estado
            ]
            pdf.tabla_fila(datos, col_widths, fill)
            fill = not fill
        
        # Total de ventas
        total_ventas = sum(v.total for v in ventas)
        pdf.tabla_total("TOTAL VENTAS", pdf.formato_moneda(total_ventas), col_widths)
    
    # Abonos realizados
    # Recopilamos todos los abonos del cliente a través de sus ventas
    todos_abonos = []
    for venta in ventas:
        if hasattr(venta, 'abonos') and venta.abonos:
            for abono in venta.abonos:
                todos_abonos.append(abono)
    
    if todos_abonos:
        pdf.ln(10)
        pdf.seccion("ABONOS REALIZADOS")
        
        # Tabla de abonos
        headers = ["Fecha", "Abono", "Factura", "Monto", "Cobrador"]
        col_widths = pdf.tabla_inicio(headers, [40, 25, 25, 50, 50])
        
        fill = False
        for abono in sorted(todos_abonos, key=lambda a: a.fecha, reverse=True):
            datos = [
                abono.fecha.strftime("%d/%m/%Y"),
                f"#{abono.id}",
                f"#{abono.venta_id}",
                pdf.formato_moneda(abono.monto),
                abono.cobrador.nombre
            ]
            pdf.tabla_fila(datos, col_widths, fill)
            fill = not fill
        
        # Total de abonos
        total_abonos = sum(a.monto for a in todos_abonos)
        pdf.tabla_total("TOTAL ABONOS", pdf.formato_moneda(total_abonos), col_widths)
    
    # Resumen de situación financiera
    pdf.ln(10)
    pdf.seccion("RESUMEN FINANCIERO")
    
    # Calcular saldo pendiente
    saldo_pendiente = sum(v.saldo_pendiente for v in ventas if v.tipo == 'credito' and v.saldo_pendiente > 0)
    
    pdf.campo("Total Compras Realizadas", pdf.formato_moneda(sum(v.total for v in ventas)))
    pdf.campo("Total Ventas a Crédito", pdf.formato_moneda(sum(v.total for v in ventas if v.tipo == 'credito')))
    pdf.campo("Total Abonos Realizados", pdf.formato_moneda(sum(a.monto for a in todos_abonos) if todos_abonos else 0))
    pdf.campo("Saldo Pendiente Actual", pdf.formato_moneda(saldo_pendiente))
    
    # Estado del cliente
    pdf.ln(5)
    pdf.set_font('Roboto', 'B', 12)
    if saldo_pendiente > 0:
        pdf.set_text_color(192, 0, 0)  # Rojo
        pdf.cell(0, 8, "ESTADO: TIENE CRÉDITOS PENDIENTES", 0, 1, 'C')
    else:
        pdf.set_text_color(0, 128, 0)  # Verde
        pdf.cell(0, 8, "ESTADO: AL DÍA, SIN SALDOS PENDIENTES", 0, 1, 'C')
    
    # Pie de página extra
    pdf.ln(10)
    pdf.set_font('Roboto', 'I', 9)
    pdf.set_text_color(100, 100, 100)
    pdf.multi_cell(0, 5, "Este documento es un reporte generado por el sistema CreditApp.\nLos datos reflejados corresponden al historial de transacciones del cliente hasta la fecha actual.")
    
    # Generar PDF en bytes
    pdf_bytes = pdf.output(dest='S')
    if isinstance(pdf_bytes, str):
        return pdf_bytes.encode('latin1')
    return bytes(pdf_bytes)
