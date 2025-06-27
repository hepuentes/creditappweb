from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    flash,
    current_app,
    jsonify,
)
from flask_login import login_required, current_user
from app.models import Venta, Cliente, Abono
from app.decorators import vendedor_cobrador_required
from datetime import datetime, timedelta
import logging
import re

# Configurar logging específico para cobros
logger = logging.getLogger("app.cobros")

cobros_bp = Blueprint("cobros", __name__, url_prefix="/cobros")


def obtener_informacion_cuotas_segura(venta):
    """Obtiene información segura de las cuotas de una venta"""
    try:
        # Valores por defecto seguros - usar campos que SÍ existen
        info = {
            "total_cuotas": 1,  # Asumir 1 cuota por defecto
            "cuotas_pagadas": 0,
            "monto_cuota": 0,
            "fecha_inicio": venta.fecha,
            "dias_entre_cuotas": 30,  # 30 días por defecto
        }

        if (
            venta.tipo == "credito"
            and venta.saldo_pendiente
            and venta.saldo_pendiente > 0
        ):
            total_abonado = sum(a.monto for a in venta.abonos if a.monto)
            monto_total = (
                venta.total
            )  # ✅ CORREGIDO: usar 'total' en lugar de 'precio_total'

            # Lógica simplificada sin usar campos inexistentes
            # Si el saldo pendiente es menor que el total, significa que ya se abonó algo
            if total_abonado > 0:
                # Calcular cuántas "cuotas" se han pagado basado en el 50% del total
                monto_por_cuota = monto_total // 2  # Dividir en 2 cuotas por defecto
                info["total_cuotas"] = 2
                info["monto_cuota"] = monto_por_cuota
                info["cuotas_pagadas"] = min(total_abonado // monto_por_cuota, 2)
            else:
                # Si no hay abonos, asumir que es 1 cuota del saldo pendiente
                info["monto_cuota"] = int(venta.saldo_pendiente)
                info["cuotas_pagadas"] = 0

        return info
    except Exception as e:
        logger.error(
            f"Error en obtener_informacion_cuotas_segura para venta {venta.id}: {e}"
        )
        return {
            "total_cuotas": 1,
            "cuotas_pagadas": 0,
            "monto_cuota": int(venta.saldo_pendiente) if venta.saldo_pendiente else 0,
            "fecha_inicio": venta.fecha,
            "dias_entre_cuotas": 30,
        }


def calcular_fecha_vencimiento_cuota(venta, numero_cuota, info_cuotas):
    """Calcula la fecha de vencimiento de una cuota específica"""
    try:
        dias_transcurridos = (datetime.now().date() - venta.fecha.date()).days
        dias_para_cuota = numero_cuota * info_cuotas["dias_entre_cuotas"]
        fecha_vencimiento = venta.fecha.date() + timedelta(days=dias_para_cuota)
        return fecha_vencimiento
    except Exception as e:
        logger.error(
            f"Error calculando fecha vencimiento para venta {venta.id}, cuota {numero_cuota}: {e}"
        )
        return datetime.now().date()


def formatear_numero_whatsapp(telefono_original):
    """
    Formatea un número de teléfono para WhatsApp
    Retorna: (telefono_final, es_valido, mensaje_error)
    """
    try:
        if not telefono_original:
            return None, False, "No hay número de teléfono registrado"

        # Convertir a string y limpiar
        telefono_str = str(telefono_original).strip()

        # Eliminar todos los caracteres no numéricos
        telefono_limpio = re.sub(r"[^\d]", "", telefono_str)

        logger.info(
            f"Número original: '{telefono_original}' -> Limpio: '{telefono_limpio}'"
        )

        # Validar longitud mínima
        if len(telefono_limpio) < 10:
            return (
                None,
                False,
                f"Número muy corto: {telefono_limpio} (mínimo 10 dígitos)",
            )

        # Validar longitud máxima
        if len(telefono_limpio) > 15:
            return (
                None,
                False,
                f"Número muy largo: {telefono_limpio} (máximo 15 dígitos)",
            )

        # Formatear para Colombia
        if len(telefono_limpio) == 10:
            # Número colombiano estándar: 3211234567
            if telefono_limpio.startswith(("3", "60", "61", "62")):
                telefono_final = "57" + telefono_limpio
            else:
                telefono_final = "57" + telefono_limpio
        elif len(telefono_limpio) == 12 and telefono_limpio.startswith("57"):
            # Ya tiene código de país Colombia: 573211234567
            telefono_final = telefono_limpio
        elif len(telefono_limpio) == 11:
            if telefono_limpio.startswith("1"):
                # Quitar el 1 inicial y agregar código de país
                telefono_final = "57" + telefono_limpio[1:]
            else:
                # Agregar código de país
                telefono_final = "57" + telefono_limpio
        else:
            # Para otros casos, usar tal como está
            telefono_final = telefono_limpio

        # Validación final: debe empezar con código de país
        if not telefono_final.startswith(("1", "2", "3", "4", "5", "6", "7", "8", "9")):
            return None, False, f"Formato de número inválido: {telefono_final}"

        logger.info(f"Número formateado final: {telefono_final}")
        return telefono_final, True, "OK"

    except Exception as e:
        logger.error(f"Error formateando número {telefono_original}: {e}")
        return None, False, f"Error procesando número: {str(e)}"


def clasificar_cobros():
    """
    Función principal para clasificar cobros por estado
    Retorna: (para_hoy, vencidos, proximos)
    """
    try:
        logger.info(
            f"Iniciando clasificación de cobros para usuario: {current_user.id} - {current_user.nombre} - Rol: {current_user.rol}"
        )

        # Base query para ventas a crédito con saldo pendiente
        query = Venta.query.filter(
            Venta.tipo == "credito",
            Venta.saldo_pendiente > 0,
            Venta.estado == "pendiente",
        )

        # Filtrar por permisos de usuario
        if current_user.is_vendedor() and not current_user.is_admin():
            query = query.filter(Venta.vendedor_id == current_user.id)
            logger.info(f"Usuario es vendedor, filtrando solo sus ventas")
        else:
            logger.info(f"Usuario es cobrador/admin, viendo todas las ventas")

        ventas = query.all()
        logger.info(f"Ventas a crédito encontradas: {len(ventas)}")

        para_hoy = []
        vencidos = []
        proximos = []

        fecha_hoy = datetime.now().date()
        logger.info(f"Fecha de hoy para comparaciones: {fecha_hoy}")

        ventas_procesadas = 0
        ventas_con_error = 0

        for i, venta in enumerate(ventas, 1):
            try:
                logger.debug(f"Procesando venta {i}/{len(ventas)}: ID {venta.id}")

                info_cuotas = obtener_informacion_cuotas_segura(venta)

                # Calcular cuota actual
                cuota_actual = info_cuotas["cuotas_pagadas"] + 1
                if cuota_actual > info_cuotas["total_cuotas"]:
                    continue  # Venta completamente pagada

                # Calcular días transcurridos y cuotas esperadas
                dias_transcurridos = (fecha_hoy - venta.fecha.date()).days
                cuotas_esperadas = min(
                    max(
                        1, (dias_transcurridos // info_cuotas["dias_entre_cuotas"]) + 1
                    ),
                    info_cuotas["total_cuotas"],
                )

                logger.debug(
                    f"Venta {venta.id}: Días transcurridos: {dias_transcurridos}, Cuotas esperadas: {cuotas_esperadas}, Cuotas pagadas: {info_cuotas['cuotas_pagadas']}, Cuota actual: {cuota_actual}, Monto cuota: {info_cuotas['monto_cuota']}"
                )

                # Usar función corregida para calcular fecha de vencimiento
                logger.info(
                    f"*** FUNCIÓN CORREGIDA EJECUTÁNDOSE *** - Venta {venta.id}, Cuota {cuota_actual}, Días transcurridos: {dias_transcurridos}"
                )
                fecha_vencimiento = calcular_fecha_vencimiento_cuota(
                    venta, cuota_actual, info_cuotas
                )

                # Calcular diferencia de días
                diferencia_dias = (fecha_hoy - fecha_vencimiento).days
                logger.info(
                    f"Venta {venta.id}: Fecha calculada: {fecha_vencimiento}, Diferencia con hoy: {diferencia_dias} días"
                )
                logger.debug(
                    f"Venta {venta.id}: Fecha venc={fecha_vencimiento}, Hoy={fecha_hoy}, Días diff={diferencia_dias}, Días hasta venc={-diferencia_dias}"
                )

                # Crear objeto de cobro
                cobro = {
                    "venta": venta,
                    "cliente": venta.cliente,
                    "numero_cuota": cuota_actual,
                    "total_cuotas": info_cuotas["total_cuotas"],
                    "monto_cuota": info_cuotas["monto_cuota"],
                    "fecha_vencimiento": fecha_vencimiento,
                    "dias_diferencia": diferencia_dias,
                }

                # Clasificar por estado
                if diferencia_dias == 0:
                    para_hoy.append(cobro)
                    logger.info(
                        f"Venta {venta.id} clasificada como 'PARA HOY' - Cliente: {venta.cliente.nombre}, Monto: ${info_cuotas['monto_cuota']:,}"
                    )
                elif diferencia_dias > 0:
                    vencidos.append(cobro)
                    logger.info(
                        f"Venta {venta.id} clasificada como 'VENCIDA' ({diferencia_dias} días) - Cliente: {venta.cliente.nombre}, Monto: ${info_cuotas['monto_cuota']:,}"
                    )
                else:
                    proximos.append(cobro)
                    logger.info(
                        f"Venta {venta.id} clasificada como 'PRÓXIMA' (vence en {abs(diferencia_dias)} días) - Cliente: {venta.cliente.nombre}, Monto: ${info_cuotas['monto_cuota']:,}"
                    )

                ventas_procesadas += 1

            except Exception as e:
                ventas_con_error += 1
                logger.error(f"Error procesando venta {venta.id}: {e}")
                continue

        logger.info(
            f"Clasificación completada - Procesadas exitosamente: {ventas_procesadas}, Con errores: {ventas_con_error}"
        )
        logger.info(
            f"RESULTADO FINAL - Para hoy: {len(para_hoy)}, Vencidos: {len(vencidos)}, Próximos: {len(proximos)}"
        )

        # Log detallado de cada categoría
        if para_hoy:
            logger.info(
                f"PARA HOY - Ejemplo: Venta {para_hoy[0]['venta'].id}, Cliente: {para_hoy[0]['cliente'].nombre}"
            )
        if vencidos:
            logger.info(
                f"VENCIDOS - Ejemplo: Venta {vencidos[0]['venta'].id}, Cliente: {vencidos[0]['cliente'].nombre}, {vencidos[0]['dias_diferencia']} días atrasado"
            )
        if proximos:
            logger.info(
                f"PRÓXIMOS - Ejemplo: Venta {proximos[0]['venta'].id}, Cliente: {proximos[0]['cliente'].nombre}"
            )

        return para_hoy, vencidos, proximos

    except Exception as e:
        logger.error(f"Error crítico en clasificar_cobros: {e}")
        current_app.logger.error(f"Error en clasificar_cobros: {e}")
        return [], [], []


@cobros_bp.route("/")
@login_required
@vendedor_cobrador_required
def gestion():
    """Página principal de gestión de cobros"""
    try:
        logger.info(
            f"Acceso a gestión de cobros por usuario: {current_user.nombre} (ID: {current_user.id})"
        )

        para_hoy, vencidos, proximos = clasificar_cobros()

        resumen = {
            "para_hoy": {
                "cantidad": len(para_hoy),
                "monto_total": sum(int(c["monto_cuota"]) for c in para_hoy),
            },
            "vencidos": {
                "cantidad": len(vencidos),
                "monto_total": sum(int(c["monto_cuota"]) for c in vencidos),
            },
            "proximos": {
                "cantidad": len(proximos),
                "monto_total": sum(int(c["monto_cuota"]) for c in proximos),
            },
        }

        logger.info(f"Renderizando template con resumen: {resumen}")

        return render_template(
            "cobros/gestion.html",
            para_hoy=para_hoy,
            vencidos=vencidos,
            proximos=proximos,
            resumen=resumen,
        )

    except Exception as e:
        logger.error(f"Error en ruta de gestión: {e}")
        current_app.logger.error(f"Error en gestión de cobros: {e}")
        flash(
            "Error al cargar la gestión de cobros. Por favor contacte al administrador.",
            "danger",
        )
        return redirect(url_for("dashboard.index"))


@cobros_bp.route("/api/estadisticas")
@login_required
@vendedor_cobrador_required
def api_estadisticas():
    """API endpoint para obtener estadísticas de cobros (para AJAX)"""
    try:
        para_hoy, vencidos, proximos = clasificar_cobros()

        estadisticas = {
            "para_hoy": len(para_hoy),
            "vencidos": len(vencidos),
            "proximos": len(proximos),
            "monto_para_hoy": sum(int(c["monto_cuota"]) for c in para_hoy),
            "monto_vencidos": sum(int(c["monto_cuota"]) for c in vencidos),
            "monto_proximos": sum(int(c["monto_cuota"]) for c in proximos),
        }

        logger.debug(f"API estadísticas devuelve: {estadisticas}")
        return jsonify(estadisticas)

    except Exception as e:
        logger.error(f"Error en API estadísticas: {e}")
        return (
            jsonify(
                {
                    "para_hoy": 0,
                    "vencidos": 0,
                    "proximos": 0,
                    "monto_para_hoy": 0,
                    "monto_vencidos": 0,
                    "monto_proximos": 0,
                    "error": str(e),
                }
            ),
            500,
        )


@cobros_bp.route("/detalle/<int:venta_id>")
@login_required
@vendedor_cobrador_required
def detalle_cobro(venta_id):
    """Muestra el detalle de un cobro específico"""
    try:
        venta = Venta.query.get_or_404(venta_id)

        # Verificar permisos
        if not current_user.is_admin():
            if current_user.is_vendedor() and venta.vendedor_id != current_user.id:
                flash("No tienes permisos para ver esta venta", "danger")
                return redirect(url_for("cobros.gestion"))

        info_cuotas = obtener_informacion_cuotas_segura(venta)

        return render_template(
            "cobros/detalle.html", venta=venta, info_cuotas=info_cuotas
        )

    except Exception as e:
        logger.error(f"Error en detalle_cobro: {e}")
        flash("Error al cargar el detalle del cobro", "danger")
        return redirect(url_for("cobros.gestion"))


@cobros_bp.route("/cliente/<int:cliente_id>")
@login_required
@vendedor_cobrador_required
def detalle_cliente(cliente_id):
    """Muestra el detalle de cobros de un cliente específico"""
    try:
        cliente = Cliente.query.get_or_404(cliente_id)

        # Obtener ventas a crédito pendientes del cliente
        query = Venta.query.filter(
            Venta.cliente_id == cliente_id,
            Venta.tipo == "credito",
            Venta.saldo_pendiente > 0,
            Venta.estado == "pendiente",
        )

        # Filtrar por permisos de usuario
        if current_user.is_vendedor() and not current_user.is_admin():
            query = query.filter(Venta.vendedor_id == current_user.id)

        ventas = query.all()

        # Procesar información de cada venta
        ventas_cliente = []
        for venta in ventas:
            try:
                info_cuotas = obtener_informacion_cuotas_segura(venta)
                cuota_actual = info_cuotas["cuotas_pagadas"] + 1

                if cuota_actual <= info_cuotas["total_cuotas"]:
                    fecha_vencimiento = calcular_fecha_vencimiento_cuota(
                        venta, cuota_actual, info_cuotas
                    )
                    dias_diferencia = (datetime.now().date() - fecha_vencimiento).days

                    venta_info = {
                        "venta": venta,
                        "cuota_actual": cuota_actual,
                        "total_cuotas": info_cuotas["total_cuotas"],
                        "monto_cuota": info_cuotas["monto_cuota"],
                        "fecha_vencimiento": fecha_vencimiento,
                        "dias_atraso": (
                            dias_diferencia if dias_diferencia > 0 else dias_diferencia
                        ),
                        "abonos": (
                            list(venta.abonos)[-5:] if venta.abonos else []
                        ),  # Últimos 5 abonos
                    }
                    ventas_cliente.append(venta_info)

            except Exception as e:
                logger.error(
                    f"Error procesando venta {venta.id} para cliente {cliente_id}: {e}"
                )
                continue

        return render_template(
            "cobros/detalle_cliente.html",
            cliente=cliente,
            ventas_cliente=ventas_cliente,
        )

    except Exception as e:
        logger.error(f"Error en detalle_cliente: {e}")
        flash("Error al cargar el detalle del cliente", "danger")
        return redirect(url_for("cobros.gestion"))


@cobros_bp.route("/whatsapp/<int:venta_id>/<tipo_cobro>")
@login_required
@vendedor_cobrador_required
def generar_whatsapp(venta_id, tipo_cobro):
    """Genera URL y mensaje de WhatsApp para un cobro específico"""
    try:
        venta = Venta.query.get_or_404(venta_id)

        # Verificar permisos
        if not current_user.is_admin():
            if current_user.is_vendedor() and venta.vendedor_id != current_user.id:
                return jsonify({"error": "No tienes permisos para esta venta"}), 403

        cliente = venta.cliente

        # Formatear número de teléfono
        telefono_final, es_valido, mensaje_error = formatear_numero_whatsapp(
            cliente.telefono
        )

        if not es_valido:
            logger.error(
                f"Error de teléfono para cliente {cliente.nombre}: {mensaje_error}"
            )
            return jsonify({"error": f"Error de teléfono: {mensaje_error}"}), 400

        # Obtener información de la cuota
        info_cuotas = obtener_informacion_cuotas_segura(venta)
        cuota_actual = info_cuotas["cuotas_pagadas"] + 1
        fecha_vencimiento = calcular_fecha_vencimiento_cuota(
            venta, cuota_actual, info_cuotas
        )

        # Formatear fechas
        fecha_hoy = datetime.now().strftime("%d/%m/%Y")
        fecha_venc_str = fecha_vencimiento.strftime("%d/%m/%Y")

        # Generar mensaje según tipo de cobro
        if tipo_cobro == "hoy":
            mensaje = f"""RECORDATORIO DE PAGO

Hola {cliente.nombre}!

Esperamos que te encuentres bien. Te recordamos que tienes una cuota que vence hoy {fecha_hoy}.

Detalles del pago:
• Venta: #{venta.id}
• Cuota: {cuota_actual} de {info_cuotas['total_cuotas']}
• Monto: ${info_cuotas['monto_cuota']:,}
• Fecha vencimiento: {fecha_venc_str}

Saldo pendiente total: ${venta.saldo_pendiente:,}

Gracias por tu preferencia! 
Si ya realizaste el pago, por favor compartenos el comprobante."""

        elif tipo_cobro == "vencido":
            dias_vencido = (datetime.now().date() - fecha_vencimiento).days
            mensaje = f"""CUOTA VENCIDA

Hola {cliente.nombre}!

Te informamos que tienes una cuota vencida desde hace {dias_vencido} dia{'s' if dias_vencido > 1 else ''}.

Detalles del pago:
• Venta: #{venta.id}
• Cuota: {cuota_actual} de {info_cuotas['total_cuotas']}
• Monto: ${info_cuotas['monto_cuota']:,}
• Fecha vencimiento: {fecha_venc_str}

Saldo pendiente total: ${venta.saldo_pendiente:,}

Por favor contactanos para ponerte al dia con tus pagos.
Estamos aqui para ayudarte!"""

        elif tipo_cobro == "proximo":
            dias_restantes = (fecha_vencimiento - datetime.now().date()).days
            mensaje = f"""RECORDATORIO DE PAGO PROXIMO

Hola {cliente.nombre}!

Te recordamos que tienes una cuota proxima a vencer en {dias_restantes} dia{'s' if dias_restantes > 1 else ''}.

Detalles del pago:
• Venta: #{venta.id}
• Cuota: {cuota_actual} de {info_cuotas['total_cuotas']}
• Monto: ${info_cuotas['monto_cuota']:,}
• Fecha vencimiento: {fecha_venc_str}

Saldo pendiente total: ${venta.saldo_pendiente:,}

Puedes adelantar tu pago para evitar inconvenientes!
Gracias por tu preferencia."""

        else:
            return jsonify({"error": "Tipo de cobro no válido"}), 400

        # Generar URL de WhatsApp usando codificación simple y segura
        # Solo codificar caracteres que realmente causan problemas
        mensaje_para_url = (
            mensaje.replace("\n", "%0A").replace(" ", "+").replace("#", "%23")
        )
        whatsapp_url = f"https://wa.me/{telefono_final}?text={mensaje_para_url}"

        logger.info(
            f"WhatsApp generado exitosamente - Venta: {venta_id}, Cliente: {cliente.nombre}, Teléfono: {telefono_final}"
        )

        return jsonify(
            {
                "url": whatsapp_url,
                "mensaje": mensaje,
                "telefono": telefono_final,
                "cliente": cliente.nombre,
            }
        )

    except Exception as e:
        logger.error(f"Error generando WhatsApp para venta {venta_id}: {e}")
        return jsonify({"error": f"Error al generar mensaje: {str(e)}"}), 500
