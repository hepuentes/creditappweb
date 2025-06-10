from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Caja, MovimientoCaja
from app.forms import MovimientoCajaForm, CajaForm
from app.decorators import (vendedor_required, cobrador_required, admin_required)

cajas_bp = Blueprint('cajas', __name__, url_prefix='/cajas')

@cajas_bp.route('/')
@login_required
def index():
    cajas = Caja.query.all()
    
    # Calcular totales por tipo
    total_efectivo = sum(c.saldo_actual for c in cajas if c.tipo == 'efectivo')
    total_nequi = sum(c.saldo_actual for c in cajas if c.tipo == 'nequi')
    total_daviplata = sum(c.saldo_actual for c in cajas if c.tipo == 'daviplata')
    total_transferencia = sum(c.saldo_actual for c in cajas if c.tipo == 'transferencia')
    total_general = sum(c.saldo_actual for c in cajas)
    
    return render_template('cajas/index.html', cajas=cajas,
                          total_efectivo=total_efectivo,
                          total_nequi=total_nequi,
                          total_daviplata=total_daviplata,
                          total_transferencia=total_transferencia,
                          total_general=total_general)

@cajas_bp.route('/crear', methods=['GET', 'POST'])
@login_required
def crear():
    form = CajaForm()
    if form.validate_on_submit():
        try:
            # Manejar explícitamente el caso de valor 0
            if form.saldo_inicial.data == 0 or form.saldo_inicial.data == "0":
                saldo_inicial = 0.0
            else:
                saldo_inicial = float(form.saldo_inicial.data)
            
            # Crear la caja con los datos validados
            caja = Caja(
                nombre=form.nombre.data,
                tipo=form.tipo.data,
                saldo_inicial=saldo_inicial,
                saldo_actual=saldo_inicial,
                fecha_apertura=datetime.now()
            )
            db.session.add(caja)
            db.session.commit()
            flash('Caja creada exitosamente', 'success')
            return redirect(url_for('cajas.index'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error al crear la caja: {str(e)}', 'danger')
    
    # Si hay errores de validación, mostrarlos
    if form.errors:
        for field, errors in form.errors.items():
            for error in errors:
                flash(f'Error en {field}: {error}', 'danger')
    
    return render_template('cajas/crear.html', form=form)

@cajas_bp.route('/<int:id>/movimientos')
@login_required
def movimientos(id):
    caja = Caja.query.get_or_404(id)
    
    # Filtrar movimientos por fecha si hay parámetros
    desde = request.args.get('desde')
    hasta = request.args.get('hasta')
    tipo = request.args.get('tipo')
    
    query = MovimientoCaja.query.filter_by(caja_id=id)
    
    if desde:
        desde_dt = datetime.strptime(desde, '%Y-%m-%d')
        query = query.filter(MovimientoCaja.fecha >= desde_dt)
    
    if hasta:
        hasta_dt = datetime.strptime(hasta, '%Y-%m-%d')
        query = query.filter(MovimientoCaja.fecha <= hasta_dt)
    
    if tipo:
        query = query.filter_by(tipo=tipo)
    
    movimientos = query.order_by(MovimientoCaja.fecha.desc()).all()
    
    # Calcular totales
    total_entradas = sum(m.monto for m in movimientos if m.tipo == 'entrada')
    total_salidas = sum(m.monto for m in movimientos if m.tipo == 'salida')
    total_transferencias = sum(m.monto for m in movimientos if m.tipo == 'transferencia')
    
    return render_template('cajas/movimientos.html', 
                           caja=caja, 
                           movimientos=movimientos,
                           desde=desde,
                           hasta=hasta,
                           tipo=tipo,
                           total_entradas=total_entradas,
                           total_salidas=total_salidas,
                           total_transferencias=total_transferencias)

@cajas_bp.route('/<int:id>/nuevo-movimiento', methods=['GET','POST'])
@login_required
def nuevo_movimiento(id):
    caja = Caja.query.get_or_404(id)
    form = MovimientoCajaForm()
    
    # Establecer tipo por defecto si viene en la URL
    tipo_param = request.args.get('tipo')
    if tipo_param and request.method == 'GET':
        form.tipo.data = tipo_param
    
    # Cargar cajas para transferencias
    from app.models import Caja as CajaModel
    form.caja_destino_id.choices = [('', 'Ninguna')] + [(c.id, c.nombre) for c in CajaModel.query.filter(CajaModel.id != id).all()]
    
    if form.validate_on_submit():
        try:
            # Validar montos
            monto = form.monto.data
            if (form.tipo.data == 'salida' or form.tipo.data == 'transferencia') and monto > caja.saldo_actual:
                flash(f"El monto no puede ser mayor al saldo actual (${caja.saldo_actual:,.2f})", 'danger')
                return render_template('cajas/nuevo_movimiento.html', form=form, caja=caja)
            
            # Crear el movimiento
            mov = MovimientoCaja(
                tipo=form.tipo.data,
                monto=monto,
                descripcion=form.concepto.data,  # ¡IMPORTANTE! Usar descripcion en lugar de concepto
                caja_id=caja.id,
                caja_destino_id=form.caja_destino_id.data if form.tipo.data == 'transferencia' else None
            )
            
            db.session.add(mov)
            
            # Actualizar saldos
            if form.tipo.data == 'entrada':
                caja.saldo_actual += monto
            elif form.tipo.data == 'salida':
                caja.saldo_actual -= monto
            elif form.tipo.data == 'transferencia' and form.caja_destino_id.data:
                caja.saldo_actual -= monto
                caja_destino = CajaModel.query.get(form.caja_destino_id.data)
                if not caja_destino:
                    flash(f"Caja destino no encontrada", 'danger')
                    return render_template('cajas/nuevo_movimiento.html', form=form, caja=caja)
                
                caja_destino.saldo_actual += monto
                
                # Crear movimiento en la caja destino
                mov_destino = MovimientoCaja(
                    tipo='entrada',
                    monto=monto,
                    descripcion=f"Transferencia desde {caja.nombre}",
                    caja_id=caja_destino.id,
                    caja_destino_id=caja.id
                )
                db.session.add(mov_destino)
            
            db.session.commit()
            flash('Movimiento registrado exitosamente', 'success')
            return redirect(url_for('cajas.movimientos', id=id))
            
        except Exception as e:
            db.session.rollback()
            flash(f"Error al registrar movimiento: {str(e)}", 'danger')
    
    return render_template('cajas/nuevo_movimiento.html', form=form, caja=caja)

@cajas_bp.route('/<int:id>/detalle')
@login_required
def detalle(id):
    caja = Caja.query.get_or_404(id)
    return render_template('cajas/detalle.html', caja=caja)

@cajas_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required  # Restringe a administradores
def editar(id):
    caja = Caja.query.get_or_404(id)
    form = CajaForm(obj=caja)
    
    if form.validate_on_submit():
        # Guardar saldo actual para calcular la diferencia
        saldo_inicial_anterior = caja.saldo_inicial
        saldo_actual_anterior = caja.saldo_actual
        
        # Actualizar nombre y tipo
        caja.nombre = form.nombre.data
        caja.tipo = form.tipo.data
        
        # Calcular el efecto en saldo_actual si cambia saldo_inicial
        if form.saldo_inicial.data != saldo_inicial_anterior:
            # Ajustar saldo_actual proporcionalmente
            diferencia = form.saldo_inicial.data - saldo_inicial_anterior
            caja.saldo_actual = saldo_actual_anterior + diferencia
            caja.saldo_inicial = form.saldo_inicial.data
            
            # Registrar este cambio como un movimiento de ajuste si hay diferencia
            if diferencia != 0:
                tipo_movimiento = 'entrada' if diferencia > 0 else 'salida'
                monto_movimiento = abs(diferencia)
                
                movimiento = MovimientoCaja(
                    caja_id=caja.id,
                    tipo=tipo_movimiento,
                    monto=monto_movimiento,
                    descripcion=f"Ajuste por modificación de saldo inicial",
                    fecha=datetime.now()
                )
                db.session.add(movimiento)
        
        # Guardar los cambios
        db.session.commit()
        flash('Caja actualizada exitosamente', 'success')
        return redirect(url_for('cajas.index'))
        
    return render_template('cajas/editar.html', form=form, caja=caja)

@cajas_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required  # Restringe a administradores
def eliminar(id):
    caja = Caja.query.get_or_404(id)
    
    # Verificar si hay movimientos asociados a esta caja
    movimientos = MovimientoCaja.query.filter_by(caja_id=id).first()
    
    if movimientos:
        flash('No se puede eliminar la caja porque tiene movimientos asociados.', 'danger')
        return redirect(url_for('cajas.index'))
    
    # Si no hay movimientos asociados, procedemos a eliminar
    try:
        nombre_caja = caja.nombre  # Guardamos para el mensaje
        db.session.delete(caja)
        db.session.commit()
        flash(f'Caja "{nombre_caja}" eliminada exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar la caja: {str(e)}', 'danger')
    
    return redirect(url_for('cajas.index'))
