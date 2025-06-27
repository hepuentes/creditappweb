from app.pdf.utils import CreditAppPDF
from datetime import datetime, timedelta


def generar_pdf_credito(credito):
    pdf = CreditAppPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.titulo("CONTRATO DE CRÉDITO")
    pdf.seccion("INFORMACIÓN DEL CRÉDITO")
    pdf.campo("Número de Crédito", f"{credito.id}")
    pdf.campo("Fecha", credito.fecha.strftime("%d/%m/%Y"))
    fecha_vencimiento = credito.fecha + timedelta(days=credito.plazo)
    pdf.campo("Fecha Vencimiento", fecha_vencimiento.strftime("%d/%m/%Y"))

    pdf.ln(3)
    pdf.seccion("INFORMACIÓN DEL CLIENTE")
    pdf.campo("Cliente", credito.cliente.nombre)
    pdf.campo("Documento", credito.cliente.cedula)
    if credito.cliente.telefono:
        pdf.campo("Teléfono", credito.cliente.telefono)
    if credito.cliente.direccion:
        pdf.campo("Dirección", credito.cliente.direccion)

    pdf.ln(3)
    pdf.seccion("CONDICIONES DEL CRÉDITO")
    pdf.campo("Monto Total", pdf.formato_moneda(credito.monto))
    pdf.campo("Plazo (días)", str(credito.plazo))
    pdf.campo("Tasa de Interés", f"{credito.tasa}%")

    interes = (credito.monto * credito.tasa) / 100
    total_pagar = credito.monto + interes

    pdf.campo("Interés", pdf.formato_moneda(interes))
    pdf.campo("Total a Pagar", pdf.formato_moneda(total_pagar))

    pdf.ln(3)
    pdf.seccion("PLAN DE PAGOS")
    headers = ["Cuota", "Fecha", "Monto", "Estado"]
    col_widths = pdf.tabla_inicio(headers, [25, 55, 50, 60])

    fecha_cuota = credito.fecha
    monto_cuota = total_pagar / 3

    fill = False
    for i in range(3):
        fecha_cuota = fecha_cuota + timedelta(days=30)
        estado = "PENDIENTE"
        if hasattr(credito, "abonos") and credito.abonos:
            total_abonado = sum(a.monto for a in credito.abonos)
            if total_abonado >= monto_cuota * (i + 1):
                estado = "PAGADO"

        datos = [
            f"{i+1}",
            fecha_cuota.strftime("%d/%m/%Y"),
            pdf.formato_moneda(monto_cuota),
            estado,
        ]
        pdf.tabla_fila(datos, col_widths, fill, [0, 2, 3])
        fill = not fill

    pdf.tabla_total("TOTAL", pdf.formato_moneda(total_pagar), col_widths)

    pdf.ln(6)
    pdf.seccion("TÉRMINOS Y CONDICIONES")
    pdf.set_font("Roboto", "", 9)
    terminos = """
1. El cliente se compromete a pagar el monto total más los intereses en los plazos establecidos.
2. Los pagos deben realizarse en la fecha indicada o antes para evitar recargos por mora.
3. El pago anticipado del crédito no genera penalización.
4. El incumplimiento en los pagos generará intereses moratorios según la tasa establecida.
5. Este documento constituye un comprobante válido del compromiso de crédito.
    """
    pdf.multi_cell(0, 4, terminos.strip())

    pdf.ln(2)
    pdf.set_font("Roboto", "B", 9)
    pdf.cell(0, 5, "Validez sin firma:", 0, 1)
    pdf.set_font("Roboto", "", 9)
    texto_validez = (
        "La expedición de este documento a través del sistema CreditApp constituye aceptación "
        "y reconocimiento pleno de las obligaciones aquí descritas, con plena validez legal, sin "
        "necesidad de firma manuscrita."
    )
    pdf.multi_cell(0, 4, texto_validez)

    pdf_bytes = pdf.output(dest="S")
    if isinstance(pdf_bytes, str):
        return pdf_bytes.encode("latin1")
    return bytes(pdf_bytes)
