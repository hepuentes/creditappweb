from app.pdf.utils import CreditAppPDF
from datetime import datetime


def generar_pdf_abono(abono):
    pdf = CreditAppPDF()
    pdf.alias_nb_pages()
    pdf.add_page()

    pdf.titulo("COMPROBANTE DE ABONO")
    pdf.seccion("INFORMACIÓN DEL ABONO")
    pdf.campo("Número de Recibo", f"{abono.id}")
    pdf.campo("Fecha", abono.fecha.strftime("%d/%m/%Y %H:%M"))
    pdf.campo("Cobrador", abono.cobrador.nombre)
    pdf.campo("Monto", pdf.formato_moneda(abono.monto))

    pdf.ln(3)
    pdf.seccion("INFORMACIÓN DEL CLIENTE")
    pdf.campo("Cliente", abono.venta.cliente.nombre)
    pdf.campo("Documento", abono.venta.cliente.cedula)
    if abono.venta.cliente.telefono:
        pdf.campo("Teléfono", abono.venta.cliente.telefono)

    pdf.ln(3)
    pdf.seccion("INFORMACIÓN DE LA VENTA")
    pdf.campo("Factura Nº", str(abono.venta_id))
    pdf.campo("Fecha de Venta", abono.venta.fecha.strftime("%d/%m/%Y"))
    pdf.campo("Valor Total", pdf.formato_moneda(abono.venta.total))
    pdf.campo(
        "Saldo Anterior", pdf.formato_moneda(abono.venta.saldo_pendiente + abono.monto)
    )
    pdf.campo("Abono Actual", pdf.formato_moneda(abono.monto))
    pdf.campo("Saldo Pendiente", pdf.formato_moneda(abono.venta.saldo_pendiente))

    if abono.notas:
        pdf.ln(3)
        pdf.seccion("NOTAS")
        pdf.set_font("Roboto", "", 10)
        pdf.multi_cell(0, 5, abono.notas)

    pdf_bytes = pdf.output(dest="S")
    if isinstance(pdf_bytes, str):
        return pdf_bytes.encode("latin1")
    return bytes(pdf_bytes)
