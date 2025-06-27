from flask import (
    Blueprint,
    render_template,
    redirect,
    url_for,
    request,
    flash,
    jsonify,
    current_app,
)
from flask_login import login_required, current_user
from app import db
from app.models import Venta, Usuario, TransferenciaVenta, Abono, Comision
from app.decorators import admin_required
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
transferencias_bp = Blueprint("transferencias", __name__, url_prefix="/transferencias")


@transferencias_bp.route("/")
@login_required
@admin_required
def index():
    """Lista todas las ventas transferibles y el historial de transferencias"""
    try:
        # Obtener ventas transferibles (solo créditos activos)
        ventas_transferibles = (
            Venta.query.filter(
                Venta.tipo == "credito",
                Venta.saldo_pendiente > 0,
                Venta.estado == "pendiente",
            )
            .order_by(Venta.fecha.desc())
            .all()
        )

        # Filtrar ventas que tengan gestor válido
        ventas_validas = []
        for venta in ventas_transferibles:
            try:
                gestor_info = venta.obtener_gestor_seguro()
                if gestor_info["usuario"]:
                    ventas_validas.append(venta)
                else:
                    logger.warning(
                        f"Venta {venta.id} no tiene gestor válido: {gestor_info.get('error', 'Gestor no encontrado')}"
                    )
            except Exception as e:
                logger.error(f"Error verificando gestor para venta {venta.id}: {e}")
                continue

        # Obtener historial de transferencias
        transferencias = (
            TransferenciaVenta.query.order_by(TransferenciaVenta.fecha.desc())
            .limit(50)
            .all()
        )

        return render_template(
            "transferencias/index.html",
            ventas_transferibles=ventas_validas,
            transferencias=transferencias,
        )
    except Exception as e:
        logger.error(f"Error en index de transferencias: {e}")
        flash("Error al cargar las transferencias", "danger")
        return redirect(url_for("dashboard.index"))


@transferencias_bp.route("/realizar/<int:venta_id>")
@login_required
@admin_required
def mostrar_transferencia(venta_id):
    """Muestra el formulario para transferir una venta específica"""
    try:
        venta = Venta.query.get_or_404(venta_id)

        # Verificar que la venta sea transferible
        if venta.tipo != "credito" or venta.saldo_pendiente <= 0:
            flash(
                "Solo se pueden transferir ventas a crédito con saldo pendiente",
                "danger",
            )
            return redirect(url_for("transferencias.index"))

        # Obtener gestor actual de forma segura
        try:
            gestor_info = venta.obtener_gestor_seguro()
            if not gestor_info["usuario"]:
                flash(
                    f'Error: La venta no tiene un gestor válido. {gestor_info.get("error", "")}',
                    "danger",
                )
                return redirect(url_for("transferencias.index"))

            gestor_actual = gestor_info["usuario"]
        except Exception as e:
            logger.error(f"Error obteniendo gestor para venta {venta_id}: {e}")
            flash("Error al determinar el gestor actual de la venta", "danger")
            return redirect(url_for("transferencias.index"))

        # Obtener usuarios disponibles (vendedores y cobradores activos)
        usuarios_disponibles = (
            Usuario.query.filter(
                Usuario.rol.in_(["vendedor", "cobrador"]),
                Usuario.activo == True,
                Usuario.id != gestor_actual.id,  # Excluir el usuario actual
            )
            .order_by(Usuario.nombre)
            .all()
        )

        return render_template(
            "transferencias/realizar.html",
            venta=venta,
            usuarios_disponibles=usuarios_disponibles,
            gestor_actual=gestor_actual,
        )
    except Exception as e:
        logger.error(f"Error en mostrar_transferencia: {e}")
        flash("Error al cargar el formulario de transferencia", "danger")
        return redirect(url_for("transferencias.index"))


@transferencias_bp.route("/ejecutar", methods=["POST"])
@login_required
@admin_required
def ejecutar_transferencia():
    """Ejecuta la transferencia de la venta"""

    venta_id = request.form.get("venta_id")
    usuario_destino_id = request.form.get("usuario_destino_id")
    motivo = request.form.get("motivo", "").strip()

    # Validaciones básicas
    if not venta_id or not usuario_destino_id:
        flash("Datos incompletos para realizar la transferencia", "danger")
        return redirect(url_for("transferencias.index"))

    try:
        with db.session.begin_nested():
            venta = Venta.query.get_or_404(venta_id)
            usuario_destino = Usuario.query.get_or_404(usuario_destino_id)

            # Verificar que la venta sea transferible
            if venta.tipo != "credito" or venta.saldo_pendiente <= 0:
                flash(
                    "Solo se pueden transferir ventas a crédito con saldo pendiente",
                    "danger",
                )
                return redirect(url_for("transferencias.index"))

            # Verificar que el usuario destino sea válido
            if (
                usuario_destino.rol not in ["vendedor", "cobrador"]
                or not usuario_destino.activo
            ):
                flash(
                    "El usuario destino debe ser un vendedor o cobrador activo",
                    "danger",
                )
                return redirect(
                    url_for("transferencias.mostrar_transferencia", venta_id=venta_id)
                )

            # Obtener gestor actual de forma segura
            try:
                gestor_info = venta.obtener_gestor_seguro()
                if not gestor_info["usuario"]:
                    raise ValueError(
                        f"Venta sin gestor válido: {gestor_info.get('error', 'Gestor no encontrado')}"
                    )
                usuario_actual = gestor_info["usuario"]
            except Exception as e:
                logger.error(f"Error obteniendo gestor actual: {e}")
                flash("Error al determinar el gestor actual de la venta", "danger")
                return redirect(
                    url_for("transferencias.mostrar_transferencia", venta_id=venta_id)
                )

            if usuario_destino.id == usuario_actual.id:
                flash(
                    "No se puede transferir a la misma persona que gestiona actualmente",
                    "danger",
                )
                return redirect(
                    url_for("transferencias.mostrar_transferencia", venta_id=venta_id)
                )

            # Configurar campos de transferencia en la venta
            if not venta.transferida:
                venta.vendedor_original_id = venta.vendedor_id
                venta.transferida = True

            venta.usuario_actual_id = usuario_destino.id
            venta.fecha_transferencia = datetime.utcnow()

            # Crear registro de transferencia
            transferencia = TransferenciaVenta(
                venta_id=venta.id,
                usuario_origen_id=usuario_actual.id,
                usuario_destino_id=usuario_destino.id,
                realizada_por_id=current_user.id,
                motivo=motivo,
            )
            db.session.add(transferencia)

        # Confirmar todos los cambios
        db.session.commit()

        flash(
            f"Venta #{venta.id} transferida exitosamente de {usuario_actual.nombre} a {usuario_destino.nombre}",
            "success",
        )
        current_app.logger.info(
            f"Transferencia realizada - Venta #{venta.id}: {usuario_actual.nombre} -> {usuario_destino.nombre} por {current_user.nombre}"
        )

        return redirect(url_for("transferencias.index"))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al transferir venta: {e}")
        flash(f"Error al transferir la venta: {str(e)}", "danger")
        return redirect(url_for("transferencias.index"))


@transferencias_bp.route("/historial/<int:venta_id>")
@login_required
@admin_required
def historial_venta(venta_id):
    """Muestra el historial completo de transferencias de una venta"""
    try:
        venta = Venta.query.get_or_404(venta_id)
        transferencias = (
            TransferenciaVenta.query.filter_by(venta_id=venta_id)
            .order_by(TransferenciaVenta.fecha.desc())
            .all()
        )

        return render_template(
            "transferencias/historial.html", venta=venta, transferencias=transferencias
        )
    except Exception as e:
        logger.error(f"Error en historial_venta: {e}")
        flash("Error al cargar el historial de transferencias", "danger")
        return redirect(url_for("transferencias.index"))


@transferencias_bp.route("/api/ventas-usuario/<int:usuario_id>")
@login_required
@admin_required
def api_ventas_usuario(usuario_id):
    """API endpoint para obtener ventas de un usuario (para AJAX)"""

    try:
        # Obtener ventas que el usuario puede gestionar
        ventas = (
            Venta.query.filter(
                Venta.tipo == "credito",
                Venta.saldo_pendiente > 0,
                Venta.estado == "pendiente",
            )
            .filter(
                db.or_(
                    db.and_(
                        Venta.transferida == False, Venta.vendedor_id == usuario_id
                    ),
                    db.and_(
                        Venta.transferida == True, Venta.usuario_actual_id == usuario_id
                    ),
                )
            )
            .all()
        )

        ventas_data = []
        for venta in ventas:
            try:
                # Verificar que la venta tenga cliente válido
                if not venta.cliente:
                    continue

                ventas_data.append(
                    {
                        "id": venta.id,
                        "cliente_nombre": venta.cliente.nombre,
                        "total": venta.total,
                        "saldo_pendiente": venta.saldo_pendiente,
                        "fecha": venta.fecha.strftime("%d/%m/%Y"),
                        "transferida": venta.transferida,
                    }
                )
            except Exception as e:
                logger.warning(f"Error procesando venta {venta.id} en API: {e}")
                continue

        return jsonify({"ventas": ventas_data})

    except Exception as e:
        current_app.logger.error(f"Error en API ventas usuario: {e}")
        return jsonify({"error": str(e)}), 500


@transferencias_bp.route("/revertir/<int:transferencia_id>", methods=["POST"])
@login_required
@admin_required
def revertir_transferencia(transferencia_id):
    """Revierte una transferencia (solo la última de una venta)"""

    try:
        with db.session.begin_nested():
            transferencia = TransferenciaVenta.query.get_or_404(transferencia_id)
            venta = transferencia.venta

            # Verificar que sea la transferencia más reciente de esta venta
            ultima_transferencia = (
                TransferenciaVenta.query.filter_by(venta_id=venta.id)
                .order_by(TransferenciaVenta.fecha.desc())
                .first()
            )

            if ultima_transferencia.id != transferencia.id:
                flash("Solo se puede revertir la transferencia más reciente", "danger")
                return redirect(
                    url_for("transferencias.historial_venta", venta_id=venta.id)
                )

            # Verificar si hay abonos posteriores
            abonos_posteriores = Abono.query.filter(
                Abono.venta_id == venta.id, Abono.fecha > transferencia.fecha
            ).count()

            if abonos_posteriores > 0:
                flash(
                    "No se puede revertir una transferencia si existen abonos posteriores.",
                    "danger",
                )
                return redirect(
                    url_for("transferencias.historial_venta", venta_id=venta.id)
                )

            # Revertir la venta al usuario origen de la transferencia
            venta.usuario_actual_id = transferencia.usuario_origen_id

            # Si al revertir, ya no quedan más transferencias, la venta deja de ser "transferida"
            transferencias_restantes = TransferenciaVenta.query.filter_by(
                venta_id=venta.id
            ).count()
            if transferencias_restantes == 1:  # Solo queda esta que vamos a eliminar
                venta.transferida = False
                venta.vendedor_original_id = None
                venta.usuario_actual_id = (
                    None  # Vuelve a ser gestionada por el vendedor original
                )
                venta.fecha_transferencia = None

            # Eliminar la transferencia
            db.session.delete(transferencia)

        # Confirmar cambios
        db.session.commit()
        flash(f"Transferencia #{transferencia.id} revertida exitosamente.", "success")
        return redirect(url_for("transferencias.historial_venta", venta_id=venta.id))

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al revertir transferencia: {e}")
        flash(f"Error al revertir la transferencia: {str(e)}", "danger")
        return redirect(url_for("transferencias.index"))


@transferencias_bp.route("/limpiar-transferencias-huerfanas")
@login_required
@admin_required
def limpiar_transferencias_huerfanas():
    """Limpia transferencias inconsistentes (solo para administradores)"""
    try:
        ventas_corregidas = 0

        # Buscar ventas marcadas como transferidas pero sin usuario_actual_id
        ventas_huerfanas = Venta.query.filter(
            Venta.transferida == True, Venta.usuario_actual_id.is_(None)
        ).all()

        for venta in ventas_huerfanas:
            # Intentar encontrar la última transferencia válida
            ultima_transferencia = (
                TransferenciaVenta.query.filter_by(venta_id=venta.id)
                .order_by(TransferenciaVenta.fecha.desc())
                .first()
            )

            if ultima_transferencia:
                # Restaurar el usuario_actual_id
                venta.usuario_actual_id = ultima_transferencia.usuario_destino_id
                ventas_corregidas += 1
                logger.info(
                    f"Corregida venta {venta.id}: usuario_actual_id = {venta.usuario_actual_id}"
                )
            else:
                # No hay transferencias registradas, marcar como no transferida
                venta.transferida = False
                venta.vendedor_original_id = None
                venta.fecha_transferencia = None
                ventas_corregidas += 1
                logger.info(f"Corregida venta {venta.id}: marcada como no transferida")

        db.session.commit()

        if ventas_corregidas > 0:
            flash(
                f"Se corrigieron {ventas_corregidas} ventas con transferencias inconsistentes",
                "success",
            )
        else:
            flash("No se encontraron transferencias inconsistentes", "info")

        return redirect(url_for("transferencias.index"))

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error limpiando transferencias huérfanas: {e}")
        flash("Error al limpiar transferencias inconsistentes", "danger")
        return redirect(url_for("transferencias.index"))
