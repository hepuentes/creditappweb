from app.pdf.utils import CreditAppPDF
from datetime import datetime, timedelta

def generar_pdf_credito(credito):
    """Genera un PDF mejorado visualmente para un contrato de crédito"""
    # Crear PDF
    pdf = CreditAppPDF()
    pdf.alias_nb_pages()
    pdf.add_page()
    
    # Título
    pdf.titulo("CONTRATO DE CRÉDITO")
    
    # Número y fecha
    pdf.seccion("INFORMACIÓN DEL CRÉDITO")
    pdf.campo("Número de Crédito", f"{credito.id}")
    pdf.campo("Fecha", credito.fecha.strftime("%d/%m/%Y"))
    fecha_vencimiento = credito.fecha + timedelta(days=credito.plazo)
    pdf.campo("Fecha Vencimiento", fecha_vencimiento.strftime("%d/%m/%Y"))
    
    # Información del cliente
    pdf.ln(5)
    pdf.seccion("INFORMACIÓN DEL CLIENTE")
    pdf.campo("Cliente", credito.cliente.nombre)
    pdf.campo("Documento", credito.cliente.cedula)
    if credito.cliente.telefono:
        pdf.campo("Teléfono", credito.cliente.telefono)
    if credito.cliente.direccion:
        pdf.campo("Dirección", credito.cliente.direccion)
    
    # Condiciones del crédito
    pdf.ln(5)
    pdf.seccion("CONDICIONES DEL CRÉDITO")
    pdf.campo("Monto Total", pdf.formato_moneda(credito.monto))
    pdf.campo("Plazo (días)", str(credito.plazo))
    pdf.campo("Tasa de Interés", f"{credito.tasa}%")
    
    # Calcular intereses y total a pagar
    interes = (credito.monto * credito.tasa) / 100
    total_pagar = credito.monto + interes
    
    pdf.campo("Interés", pdf.formato_moneda(interes))
    pdf.campo("Total a Pagar", pdf.formato_moneda(total_pagar))
    
    # Plan de pagos
    pdf.ln(5)
    pdf.seccion("PLAN DE PAGOS")
    
    # Tabla de pagos
    headers = ["Cuota", "Fecha", "Monto", "Estado"]
    col_widths = pdf.tabla_inicio(headers, [20, 60, 60, 50])
    
    # Calcular fechas de pago
    # Suponemos pagos mensuales para este ejemplo
    fecha_cuota = credito.fecha
    monto_cuota = total_pagar / 3  # 3 cuotas como ejemplo
    
    fill = False
    for i in range(3):  # 3 cuotas como ejemplo
        fecha_cuota = fecha_cuota + timedelta(days=30)
        estado = "PENDIENTE"  # Por defecto todas pendientes
        
        # Si hay abonos, verificar si esta cuota está pagada
        if hasattr(credito, 'abonos') and credito.abonos:
            total_abonado = sum(a.monto for a in credito.abonos)
            if total_abonado >= monto_cuota * (i + 1):
                estado = "PAGADO"
        
        datos = [
            f"{i+1}",
            fecha_cuota.strftime("%d/%m/%Y"),
            pdf.formato_moneda(monto_cuota),
            estado
        ]
        pdf.tabla_fila(datos, col_widths, fill)
        fill = not fill
    
    # Tabla total
    pdf.tabla_total("TOTAL", pdf.formato_moneda(total_pagar), col_widths)
    
    # Términos y condiciones
    pdf.ln(10)
    pdf.seccion("TÉRMINOS Y CONDICIONES")
    pdf.set_font('Roboto', '', 9)
    terminos = """
1. El cliente se compromete a pagar el monto total más los intereses en los plazos establecidos.
2. Los pagos deben realizarse en la fecha indicada o antes para evitar recargos por mora.
3. El pago anticipado del crédito no genera penalización.
4. El incumplimiento en los pagos generará intereses moratorios según la tasa establecida.
5. Este documento constituye un comprobante válido del compromiso de crédito.
    """
    pdf.multi_cell(0, 5, terminos.strip())
    
    # Firmas
    pdf.ln(15)
    pdf.set_font('Roboto', '', 10)
    
    # Líneas para firmas
    pdf.line(30, pdf.get_y() + 20, 90, pdf.get_y() + 20)  # Línea para firma cliente
    pdf.line(120, pdf.get_y() + 20, 180, pdf.get_y() + 20)  # Línea para firma acreedor
    
    # Textos de firma
    pdf.set_xy(30, pdf.get_y() + 22)
    pdf.cell(60, 5, "Firma Cliente", 0, 0, 'C')
    
    pdf.set_xy(120, pdf.get_y())
    pdf.cell(60, 5, "Firma Autorizada", 0, 1, 'C')
    
    # Generar PDF en bytes
    pdf_bytes = pdf.output(dest='S')
    if isinstance(pdf_bytes, str):
        return pdf_bytes.encode('latin1')
    return bytes(pdf_bytes)
