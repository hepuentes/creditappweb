from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Venta, Usuario, TransferenciaVenta, Abono, Comision
from app.decorators import admin_required
from datetime import datetime

transferencias_bp = Blueprint('transferencias', __name__, url_prefix='/transferencias')

@transferencias_bp.route('/')
@login_required
@admin_required
def index():
    """Lista todas las ventas transferibles y el historial de transferencias"""
    
    # Obtener ventas transferibles (solo créditos activos)
    ventas_transferibles = Venta.query.filter(
        Venta.tipo == 'credito',
        Venta.saldo_pendiente > 0,
        Venta.estado == 'pendiente'
    ).order_by(Venta.fecha.desc()).all()
    
    # Obtener historial de transferencias
    transferencias = TransferenciaVenta.query.order_by(
        TransferenciaVenta.fecha.desc()
    ).limit(50).all()
    
    return render_template('transferencias/index.html', 
                         ventas_transferibles=ventas_transferibles,
                         transferencias=transferencias)

@transferencias_bp.route('/realizar/<int:venta_id>')
@login_required
@admin_required
def mostrar_transferencia(venta_id):
    """Muestra el formulario para transferir una venta específica"""
    
    venta = Venta.query.get_or_404(venta_id)
    
    # Verificar que la venta sea transferible
    if venta.tipo != 'credito' or venta.saldo_pendiente <= 0:
        flash('Solo se pueden transferir ventas a crédito con saldo pendiente', 'danger')
        return redirect(url_for('transferencias.index'))
    
    # Obtener usuarios disponibles (vendedores y cobradores activos)
    usuarios_disponibles = Usuario.query.filter(
        Usuario.rol.in_(['vendedor', 'cobrador']),
        Usuario.activo == True,
        Usuario.id != venta.usuario_gestor().id  # Excluir el usuario actual
    ).order_by(Usuario.nombre).all()
    
    return render_template('transferencias/realizar.html', 
                         venta=venta, 
                         usuarios_disponibles=usuarios_disponibles)

@transferencias_bp.route('/ejecutar', methods=['POST'])
@login_required
@admin_required
def ejecutar_transferencia():
    """Ejecuta la transferencia de la venta"""
    
    venta_id = request.form.get('venta_id')
    usuario_destino_id = request.form.get('usuario_destino_id')
    motivo = request.form.get('motivo', '').strip()
    
    # Validaciones básicas
    if not venta_id or not usuario_destino_id:
        flash('Datos incompletos para realizar la transferencia', 'danger')
        return redirect(url_for('transferencias.index'))

    try:
        venta = Venta.query.get_or_404(venta_id)
        usuario_destino = Usuario.query.get_or_404(usuario_destino_id)
        
        # Verificar que la venta sea transferible
        if venta.tipo != 'credito' or venta.saldo_pendiente <= 0:
            flash('Solo se pueden transferir ventas a crédito con saldo pendiente', 'danger')
            return redirect(url_for('transferencias.index'))
        
        # Verificar que el usuario destino sea válido
        if usuario_destino.rol not in ['vendedor', 'cobrador'] or not usuario_destino.activo:
            flash('El usuario destino debe ser un vendedor o cobrador activo', 'danger')
            return redirect(url_for('transferencias.mostrar_transferencia', venta_id=venta_id))
        
        usuario_actual = venta.usuario_gestor()
        if usuario_destino.id == usuario_actual.id:
            flash('No se puede transferir a la misma persona que gestiona actualmente', 'danger')
            return redirect(url_for('transferencias.mostrar_transferencia', venta_id=venta_id))
        
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
            motivo=motivo
        )
        db.session.add(transferencia)
        
        db.session.commit()
        
        flash(f'Venta #{venta.id} transferida exitosamente de {usuario_actual.nombre} a {usuario_destino.nombre}', 'success')
        current_app.logger.info(f"Transferencia realizada - Venta #{venta.id}: {usuario_actual.nombre} -> {usuario_destino.nombre} por {current_user.nombre}")
        
        return redirect(url_for('transferencias.index'))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al transferir venta: {e}")
        flash(f'Error al transferir la venta: {str(e)}', 'danger')
        return redirect(url_for('transferencias.index'))

@transferencias_bp.route('/historial/<int:venta_id>')
@login_required
@admin_required
def historial_venta(venta_id):
    """Muestra el historial completo de transferencias de una venta"""
    
    venta = Venta.query.get_or_404(venta_id)
    transferencias = TransferenciaVenta.query.filter_by(venta_id=venta_id).order_by(
        TransferenciaVenta.fecha.desc()
    ).all()
    
    return render_template('transferencias/historial.html', 
                         venta=venta, 
                         transferencias=transferencias)

@transferencias_bp.route('/api/ventas-usuario/<int:usuario_id>')
@login_required
@admin_required
def api_ventas_usuario(usuario_id):
    """API endpoint para obtener ventas de un usuario (para AJAX)"""
    
    try:
        ventas = Venta.query.filter(
            Venta.tipo == 'credito',
            Venta.saldo_pendiente > 0,
            Venta.estado == 'pendiente'
        ).filter(
            db.or_(
                db.and_(Venta.transferida == False, Venta.vendedor_id == usuario_id),
                db.and_(Venta.transferida == True, Venta.usuario_actual_id == usuario_id)
            )
        ).all()
        
        ventas_data = []
        for venta in ventas:
            ventas_data.append({
                'id': venta.id,
                'cliente_nombre': venta.cliente.nombre,
                'total': venta.total,
                'saldo_pendiente': venta.saldo_pendiente,
                'fecha': venta.fecha.strftime('%d/%m/%Y'),
                'transferida': venta.transferida
            })
        
        return jsonify({'ventas': ventas_data})
        
    except Exception as e:
        current_app.logger.error(f"Error en API ventas usuario: {e}")
        return jsonify({'error': str(e)}), 500

@transferencias_bp.route('/revertir/<int:transferencia_id>', methods=['POST'])
@login_required
@admin_required
def revertir_transferencia(transferencia_id):
    """Revierte una transferencia (solo la última de una venta)"""
    
    try:
        with db.session.begin_nested():
            transferencia = TransferenciaVenta.query.get_or_404(transferencia_id)
            venta = transferencia.venta
            
            # Verificar que sea la transferencia más reciente de esta venta
            ultima_transferencia = TransferenciaVenta.query.filter_by(
                venta_id=venta.id
            ).order_by(TransferenciaVenta.fecha.desc()).first()
            
            if ultima_transferencia.id != transferencia.id:
                flash('Solo se puede revertir la transferencia más reciente', 'danger')
                return redirect(url_for('transferencias.historial_venta', venta_id=venta.id))
            
            # Verificar si hay abonos posteriores
            abonos_posteriores = Abono.query.filter(
                Abono.venta_id == venta.id,
                Abono.fecha > transferencia.fecha
            ).count()
            
            if abonos_posteriores > 0:
                flash('No se puede revertir una transferencia si existen abonos posteriores.', 'danger')
                return redirect(url_for('transferencias.historial_venta', venta_id=venta.id))
            
            # Revertir la venta al usuario origen de la transferencia
            venta.usuario_actual_id = transferencia.usuario_origen_id
            
            # Si al revertir, ya no quedan más transferencias, la venta deja de ser "transferida"
            if TransferenciaVenta.query.filter_by(venta_id=venta.id).count() == 1:
                venta.transferida = False
                venta.vendedor_original_id = None
                venta.usuario_actual_id = None # Vuelve a ser gestionada por el vendedor original
            
            # Eliminar la transferencia en lugar de crear una reversión, para mantener la limpieza
            db.session.delete(transferencia)
            
            db.session.commit()
            flash(f'Transferencia #{transferencia.id} revertida exitosamente.', 'success')
            return redirect(url_for('transferencias.historial_venta', venta_id=venta.id))
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error al revertir transferencia: {e}")
        flash(f'Error al revertir la transferencia: {str(e)}', 'danger')
        return redirect(url_for('transferencias.index'))