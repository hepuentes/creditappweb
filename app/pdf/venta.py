from app.pdf.utils import CreditAppPDF
from datetime import datetime, timedelta


def generar_pdf_venta(venta):
    pdf = CreditAppPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.titulo("FACTURA DE VENTA")
    pdf.seccion("INFORMACIÓN DE LA VENTA")
    pdf.campo("Número de Factura", f"{venta.id}")
    pdf.campo("Fecha", venta.fecha.strftime("%d/%m/%Y %H:%M"))
    pdf.campo("Tipo", "CONTADO" if venta.tipo == "contado" else "CRÉDITO")
    pdf.campo("Estado", "PAGADO" if venta.estado == "pagado" else "PENDIENTE")

    pdf.ln(3)
    pdf.seccion("INFORMACIÓN DEL CLIENTE")
    pdf.campo("Cliente", venta.cliente.nombre)
    pdf.campo("Documento", venta.cliente.cedula)
    if venta.cliente.telefono:
        pdf.campo("Teléfono", venta.cliente.telefono)
    if venta.cliente.direccion:
        pdf.campo("Dirección", venta.cliente.direccion)

    pdf.ln(3)
    pdf.seccion("DETALLE DE PRODUCTOS")
    headers = ["Cantidad", "Producto", "Precio Unit.", "Subtotal"]
    col_widths = pdf.tabla_inicio(headers, [22, 98, 35, 35])

    fill = False
    centrar_columnas = [0, 2, 3]
    for detalle in venta.detalles:
        datos = [
            str(detalle.cantidad),
            detalle.producto.nombre,
            pdf.formato_moneda(detalle.precio_unitario),
            pdf.formato_moneda(detalle.subtotal),
        ]
        pdf.tabla_fila(datos, col_widths, fill, centrar_columnas)
        fill = not fill

    pdf.tabla_total("TOTAL", pdf.formato_moneda(venta.total), col_widths)

    # Si es venta a crédito, agregar info de pagos, abonos y términos y condiciones
    if venta.tipo == "credito":
        pdf.ln(5)
        pdf.seccion("INFORMACIÓN DE PAGO")
        pdf.campo("Saldo Pendiente", pdf.formato_moneda(venta.saldo_pendiente))

        pdf.ln(3)
        pdf.seccion("PLAN DE PAGOS")
        frecuencia = "Quincenal"
        num_cuotas = 4
        valor_cuota = venta.saldo_pendiente / num_cuotas
        fecha_primer_pago = venta.fecha + timedelta(days=15)

        pdf.campo("Frecuencia de pago", frecuencia)
        pdf.campo("Valor de cada cuota", pdf.formato_moneda(valor_cuota))
        pdf.campo("Número de cuotas", str(num_cuotas))
        pdf.campo(
            "Fecha primer pago", fecha_primer_pago.strftime("%d/%m/%Y") + " (aprox)"
        )

        pdf.ln(3)
        pdf.set_font("Roboto", "B", 11)
        pdf.set_text_color(0, 51, 102)
        pdf.cell(0, 6, "CRONOGRAMA DE PAGOS", 0, 1)

        headers_cuotas = ["Cuota", "Fecha", "Valor", "Estado"]
        col_widths_cuotas = pdf.tabla_inicio(headers_cuotas, [25, 55, 50, 60])

        fecha_cuota = fecha_primer_pago
        total_abonado = sum(a.monto for a in venta.abonos) if venta.abonos else 0

        for i in range(num_cuotas):
            cuota_num = i + 1
            estado = (
                "PAGADO" if total_abonado >= valor_cuota * cuota_num else "PENDIENTE"
            )
            datos_cuota = [
                str(cuota_num),
                fecha_cuota.strftime("%d/%m/%Y"),
                pdf.formato_moneda(valor_cuota),
                estado,
            ]
            pdf.tabla_fila(datos_cuota, col_widths_cuotas, i % 2 == 0, [0, 2])
            fecha_cuota += timedelta(days=15)

        if venta.abonos and len(venta.abonos) > 0:
            pdf.ln(3)
            pdf.seccion("ABONOS REALIZADOS")
            headers_abonos = ["Fecha", "Monto", "Cobrador"]
            col_widths_abonos = pdf.tabla_inicio(headers_abonos, [65, 45, 80])
            fill = False
            for abono in venta.abonos:
                datos_abono = [
                    abono.fecha.strftime("%d/%m/%Y"),
                    pdf.formato_moneda(abono.monto),
                    abono.cobrador.nombre,
                ]
                pdf.tabla_fila(datos_abono, col_widths_abonos, fill, [1])
                fill = not fill

        # Términos y condiciones al final con fuente más pequeña para evitar solapamiento
        pdf.ln(4)  # Reducido el espaciado antes de términos
        pdf.set_font("Roboto", "B", 8)  # Reducido de 10 a 8
        pdf.set_text_color(0, 0, 0)
        pdf.cell(0, 4, "Términos y condiciones:", 0, 1)  # Reducido height de 5 a 4
        pdf.set_font("Roboto", "", 7)  # Reducido de 9 a 7 para el texto
        terminos = (
            "1. El cliente se compromete a pagar el monto total más los intereses en los plazos establecidos.\n"
            "2. Los pagos deben realizarse en la fecha indicada o antes para evitar recargos por mora.\n"
            "3. El pago anticipado del crédito no genera penalización.\n"
            "4. El incumplimiento en los pagos generará intereses moratorios según la tasa establecida.\n"
            "5. Este documento constituye un comprobante válido del compromiso de crédito."
        )
        pdf.multi_cell(0, 3, terminos)  # Reducido line height de 4 a 3

    # Generar PDF en bytes
    pdf_bytes = pdf.output(dest="S")
    if isinstance(pdf_bytes, str):
        return pdf_bytes.encode("latin1")
    return bytes(pdf_bytes)
