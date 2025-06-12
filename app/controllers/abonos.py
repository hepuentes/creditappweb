from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response, current_app, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from app import db
from app.models import Abono, Cliente, Credito, CreditoVenta, Venta, Caja, MovimientoCaja, TransferenciaVenta
from app.forms import AbonoForm, AbonoEditForm
from app.decorators import cobrador_required, vendedor_cobrador_required, admin_required
from app.utils import registrar_movimiento_caja, calcular_comision
from app.pdf.abono import generar_pdf_abono
from datetime import datetime
import logging
from decimal import Decimal, InvalidOperation
from app.utils import shorten_url

abonos_bp = Blueprint('abonos', __name__, url_prefix='/abonos')

@abonos_bp.route('/')
@login_required
@vendedor_cobrador_required
def index():
    # Obtener parámetros de filtro
    busqueda = request.args.get('busqueda', '')
    desde_str = request.args.get('desde', '')
    hasta_str = request.args.get('hasta', '')
    
    # Consulta base
    query = Abono.query.join(Venta).join(Cliente)
    
    # Si el usuario no es administrador, filtrar abonos
    if not current_user.is_admin():
        # Un vendedor puede ver abonos de sus ventas (originales o transferidas a él)
        if current_user.is_vendedor():
            query = query.filter(
                db.or_(
                    db.and_( # Ventas originales del vendedor
                        Venta.vendedor_id == current_user.id,
                        Venta.transferida == False
                    ),
                    db.and_( # Ventas transferidas al vendedor
                        Venta.transferida == True,
                        Venta.usuario_actual_id == current_user.id
                    ),
                    Abono.cobrador_id == current_user.id # Abonos realizados por el mismo
                )
            )
        # Un cobrador puede ver abonos de ventas que gestiona o de cualquier venta no transferida
        elif current_user.is_cobrador():
            query = query.filter(
                db.or_(
                    db.and_( # Ventas transferidas al cobrador
                        Venta.transferida == True,
                        Venta.usuario_actual_id == current_user.id
                    ),
                    Abono.cobrador_id == current_user.id, # Abonos realizados por el mismo
                    db.and_( # Cualquier venta a crédito no transferida
                        Venta.tipo == 'credito',
                        Venta.transferida == False
                    )
                )
            )

    # Aplicar filtros de búsqueda
    if busqueda:
        # La búsqueda se realiza sobre el nombre del cliente
        query = query.filter(Cliente.nombre.ilike(f"%{busqueda}%"))

    if desde_str:
        try:
            desde_dt = datetime.strptime(desde_str, '%Y-%m-%d')
            query = query.filter(Abono.fecha >= desde_dt)
        except ValueError:
            flash('Fecha "desde" inválida.', 'warning')

    if hasta_str:
        try:
            hasta_dt = datetime.strptime(hasta_str, '%Y-%m-%d')
            # Incluir todo el día de la fecha "hasta"
            hasta_dt_fin_dia = datetime.combine(hasta_dt, datetime.max.time())
            query = query.filter(Abono.fecha <= hasta_dt_fin_dia)
        except ValueError:
            flash('Fecha "hasta" inválida.', 'warning')

    # Ordenar por fecha de abono descendente
    abonos = query.order_by(Abono.fecha.desc()).all()
    
    # Calcular el total de los abonos filtrados
    total_abonos = sum(a.monto for a in abonos) if abonos else 0

    return render_template('abonos/index.html', 
                           abonos=abonos, 
                           total_abonos=total_abonos,
                           busqueda=busqueda,
                           desde=desde_str,
                           hasta=hasta_str)

@abonos_bp.route('/crear', methods=['GET', 'POST'])
@login_required
@vendedor_cobrador_required
def crear():
    # Obtener IDs de la URL para preseleccionar
    cliente_id = request.args.get('cliente_id', type=int)
    venta_id = request.args.get('venta_id', type=int)
    
    # Inicializar el formulario
    form = AbonoForm()
    
    # Cargar Cajas
    cajas = Caja.query.all()
    form.caja_id.choices = [(c.id, f"{c.nombre} ({c.tipo})") for c in cajas] if cajas else [(0, "No hay cajas disponibles")]
    
    # Cargar Clientes con deudas
    clientes_query = Cliente.query.join(Venta).filter(
        Venta.tipo == 'credito', 
        Venta.saldo_pendiente > 0
    ).distinct()

    # Si no es admin, filtrar por clientes que el usuario puede gestionar
    if not current_user.is_admin():
        if current_user.is_vendedor():
            clientes_query = clientes_query.filter(
                db.or_(
                    Venta.vendedor_id == current_user.id,
                    Venta.usuario_actual_id == current_user.id
                )
            )
        elif current_user.is_cobrador():
             clientes_query = clientes_query.filter(
                db.or_(
                    Venta.transferida == False,
                    Venta.usuario_actual_id == current_user.id
                )
            )

    clientes = clientes_query.order_by(Cliente.nombre).all()
    form.cliente_id.choices = [(-1, "Seleccionar cliente")] + [(c.id, c.nombre) for c in clientes]
    
    # El selector de ventas se carga dinámicamente con JS
    form.venta_id.choices = [(-1, "Seleccione un cliente primero")]
    
    if request.method == 'POST':
        # Validación manual porque el formulario WTForms tiene campos opcionales
        validation_errors = []
        
        # Cliente
        cliente_id_form = request.form.get('cliente_id')
        if not cliente_id_form or cliente_id_form == '-1':
            validation_errors.append("Debe seleccionar un cliente.")
            
        # Venta
        venta_id_form = request.form.get('venta_id')
        if not venta_id_form or venta_id_form == '-1':
            validation_errors.append("Debe seleccionar una venta.")
            
        # Monto
        monto_form = request.form.get('monto', '').strip()
        if not monto_form:
            validation_errors.append("Debe ingresar un monto.")
            
        # Caja
        caja_id_form = request.form.get('caja_id')
        if not caja_id_form:
            validation_errors.append("Debe seleccionar una caja.")
            
        monto_decimal = None
        if monto_form:
            try:
                # Limpiar el formato del monto antes de convertir
                monto_limpio = monto_form.replace('.', '').replace(',', '.')
                monto_decimal = Decimal(monto_limpio)
                if monto_decimal <= 0:
                    validation_errors.append("El monto debe ser un número positivo.")
            except InvalidOperation:
                validation_errors.append("El formato del monto no es válido. Use solo números.")

        # Validar monto contra saldo pendiente de la venta
        if venta_id_form and venta_id_form != '-1' and monto_decimal is not None:
            venta_form = Venta.query.get(int(venta_id_form))
            if not venta_form:
                validation_errors.append("La venta seleccionada no es válida.")
            elif venta_form.saldo_pendiente < monto_decimal:
                saldo_formateado = "{:,.0f}".format(venta_form.saldo_pendiente).replace(",", ".")
                validation_errors.append(f"El monto no puede exceder el saldo pendiente de ${saldo_formateado}.")
        
        # Si no hay errores, se procede a guardar
        if not validation_errors:
            try:
                with db.session.begin_nested():
                    venta_seleccionada = Venta.query.with_for_update().get(int(venta_id_form))
                    
                    # Crear la instancia del abono
                    nuevo_abono = Abono(
                        venta_id=venta_seleccionada.id,
                        monto=int(monto_decimal), # Convertir a entero
                        cobrador_id=current_user.id,
                        caja_id=int(caja_id_form),
                        notas=request.form.get('notas', '').strip()
                    )
                    
                    # Actualizar el saldo pendiente de la venta
                    venta_seleccionada.saldo_pendiente -= int(monto_decimal)
                    
                    # Marcar como pagada si el saldo es cero o menos
                    if venta_seleccionada.saldo_pendiente <= 0:
                        venta_seleccionada.estado = 'pagado'
                        venta_seleccionada.saldo_pendiente = 0 # Asegurar que no sea negativo
                    
                    db.session.add(nuevo_abono)
                    
                    # Registrar movimiento en la caja
                    registrar_movimiento_caja(
                        caja_id=nuevo_abono.caja_id,
                        tipo='entrada',
                        monto=nuevo_abono.monto,
                        concepto=f'Abono a venta #{venta_seleccionada.id}',
                        abono_id=nuevo_abono.id,
                        venta_id=venta_seleccionada.id
                    )
                    
                    # Calcular comisión sobre el abono
                    calcular_comision(
                        monto_pagado=float(nuevo_abono.monto),
                        usuario_id=current_user.id,
                        venta_id=None,
                        abono_id=nuevo_abono.id
                    )
                
                db.session.commit()
                
                monto_formateado = "{:,.0f}".format(nuevo_abono.monto).replace(",", ".")
                flash(f'Abono de ${monto_formateado} registrado exitosamente.', 'success')
                return redirect(url_for('abonos.index'))

            except SQLAlchemyError as e:
                db.session.rollback()
                current_app.logger.error(f"Error de base de datos al registrar abono: {e}")
                flash('Error de base de datos. No se pudo registrar el abono. Intente nuevamente.', 'danger')
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error inesperado al crear abono: {e}")
                flash(f'Ocurrió un error inesperado al procesar el abono: {str(e)}', 'danger')
        else:
            # Si hay errores de validación, mostrarlos
            for error in validation_errors:
                flash(error, 'danger')

    # Para peticiones GET o si falla el POST
    return render_template('abonos/crear.html', form=form, clientes=clientes, cliente_id=cliente_id, venta_id=venta_id)


@abonos_bp.route('/cargar-ventas/<int:cliente_id>')
@login_required
@vendedor_cobrador_required
def cargar_ventas(cliente_id):
    """
    Endpoint para cargar las ventas a crédito de un cliente específico vía AJAX.
    """
    try:
        # Query base: ventas a crédito con saldo pendiente del cliente
        query = Venta.query.filter(
            Venta.cliente_id == cliente_id,
            Venta.tipo == 'credito',
            Venta.saldo_pendiente > 0
        )
        
        # Filtrar por permisos del usuario actual
        if not current_user.is_admin():
            # El usuario debe poder gestionar la venta para que aparezca en la lista
            query = query.filter(
                db.or_(
                    Venta.usuario_actual_id == current_user.id,
                    db.and_(
                        Venta.transferida == False,
                        Venta.vendedor_id == current_user.id
                    )
                )
            )

        ventas = query.all()
        
        # Formatear la respuesta para el selector
        ventas_json = []
        if ventas:
            for v in ventas:
                saldo_formateado = "{:,.0f}".format(v.saldo_pendiente).replace(",", ".")
                ventas_json.append({
                    'id': int(v.id),
                    'texto': f"Venta #{v.id} - {v.fecha.strftime('%d/%m/%Y')} - Saldo: ${saldo_formateado}"
                })
        
        return jsonify(ventas_json)
    except Exception as e:
        current_app.logger.error(f"Error en cargar_ventas para cliente {cliente_id}: {e}")
        return jsonify([]), 500


def puede_gestionar_venta_para_abono(venta, usuario):
    """
    Función de ayuda para verificar si un usuario puede hacer abonos a una venta,
    considerando roles y transferencias.
    """
    if usuario.is_admin():
        return True
    
    if usuario.is_vendedor():
        # Puede abonar a sus ventas originales no transferidas o a las que le fueron transferidas
        return (not venta.transferida and venta.vendedor_id == usuario.id) or \
               (venta.transferida and venta.usuario_actual_id == usuario.id)
    
    if usuario.is_cobrador():
        # Puede abonar a cualquier venta no transferida o a las que le fueron transferidas
        return not venta.transferida or (venta.transferida and venta.usuario_actual_id == usuario.id)
    
    return False


@abonos_bp.route('/<int:id>')
@login_required
@vendedor_cobrador_required
def detalle(id):
    abono = Abono.query.get_or_404(id)
    
    # Verificar permisos para ver el detalle del abono
    if not current_user.is_admin():
        puede_ver = False
        # Si el usuario puede gestionar la venta a la que pertenece el abono
        if puede_gestionar_venta_para_abono(abono.venta, current_user):
            puede_ver = True
        # Si el usuario fue quien registró el abono
        if abono.cobrador_id == current_user.id:
            puede_ver = True
        
        if not puede_ver:
            flash('No tienes permiso para ver los detalles de este abono.', 'danger')
            return redirect(url_for('abonos.index'))
    
    # Información de transferencia para mostrar en la vista
    info_transferencia = None
    if abono.venta.transferida:
        info_transferencia = {
            'vendedor_original': abono.venta.vendedor_original.nombre if abono.venta.vendedor_original else 'N/A',
            'usuario_actual': abono.venta.usuario_actual.nombre if abono.venta.usuario_actual else 'N/A',
            'fecha_transferencia': abono.venta.fecha_transferencia
        }
    
    return render_template('abonos/detalle.html', 
                           abono=abono, 
                           info_transferencia=info_transferencia)


@abonos_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required # Solo administradores pueden editar abonos
def editar(id):
    abono = Abono.query.get_or_404(id)
    form = AbonoEditForm(obj=abono)
    
    # Cargar cajas
    cajas = Caja.query.all()
    form.caja_id.choices = [(c.id, f"{c.nombre} ({c.tipo})") for c in cajas] if cajas else [(0, "No hay cajas disponibles")]
    
    if form.validate_on_submit():
        try:
            with db.session.begin_nested():
                # Guardar valores originales antes de la edición
                monto_original = abono.monto
                caja_original_id = abono.caja_id
                
                venta = abono.venta
                
                # Revertir el saldo en la venta
                venta.saldo_pendiente += monto_original
                
                # Actualizar el abono con los nuevos datos del formulario
                form.populate_obj(abono)
                
                # Aplicar el nuevo monto al saldo de la venta
                venta.saldo_pendiente -= abono.monto
                
                # Actualizar estado de la venta
                if venta.saldo_pendiente <= 0:
                    venta.estado = 'pagado'
                    venta.saldo_pendiente = 0
                else:
                    venta.estado = 'pendiente'
                
                # Actualizar los movimientos de caja
                # Se podría eliminar el antiguo y crear uno nuevo, o actualizarlo
                movimiento = MovimientoCaja.query.filter_by(abono_id=abono.id).first()
                if movimiento:
                    # Revertir el saldo en la caja original si cambió
                    if caja_original_id != abono.caja_id:
                        caja_original = Caja.query.get(caja_original_id)
                        if caja_original:
                            caja_original.saldo_actual -= monto_original
                        caja_nueva = Caja.query.get(abono.caja_id)
                        if caja_nueva:
                            caja_nueva.saldo_actual += abono.monto
                    else: # Si la caja es la misma, solo ajustar la diferencia
                        caja = Caja.query.get(caja_original_id)
                        if caja:
                            caja.saldo_actual = caja.saldo_actual - monto_original + abono.monto

                    # Actualizar datos del movimiento
                    movimiento.caja_id = abono.caja_id
                    movimiento.monto = abono.monto
                    movimiento.descripcion = f'Abono a venta #{venta.id} (editado)'
                    
            db.session.commit()
            flash('Abono actualizado correctamente.', 'success')
            return redirect(url_for('abonos.detalle', id=abono.id))
            
        except SQLAlchemyError as e:
            db.session.rollback()
            flash('Error de base de datos al actualizar. No se guardaron los cambios.', 'danger')
            current_app.logger.error(f"Error al editar abono {id}: {e}")
        except Exception as e:
            db.session.rollback()
            flash('Ocurrió un error inesperado al actualizar.', 'danger')
            current_app.logger.error(f"Error inesperado al editar abono {id}: {e}")
            
    return render_template('abonos/editar.html', form=form, abono=abono)


@abonos_bp.route('/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_required # Solo administradores pueden eliminar abonos
def eliminar(id):
    abono = Abono.query.get_or_404(id)
    try:
        with db.session.begin_nested():
            # Revertir el saldo de la venta
            venta = abono.venta
            venta.saldo_pendiente += abono.monto
            # Si estaba pagada, ahora vuelve a estar pendiente
            if venta.estado == 'pagado':
                venta.estado = 'pendiente'
            
            # Revertir (eliminar) el movimiento de caja asociado
            movimiento = MovimientoCaja.query.filter_by(abono_id=abono.id).first()
            if movimiento:
                caja = movimiento.caja
                if caja:
                    caja.saldo_actual -= movimiento.monto
                db.session.delete(movimiento)
            
            # Eliminar la comisión asociada si existe
            comision = Comision.query.filter_by(abono_id=abono.id).first()
            if comision:
                db.session.delete(comision)

            # Finalmente, eliminar el abono
            db.session.delete(abono)
            
        db.session.commit()
        flash('El abono ha sido eliminado y los saldos han sido restaurados.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash('Error de base de datos. No se pudo eliminar el abono.', 'danger')
        current_app.logger.error(f"Error al eliminar abono {id}: {e}")
    except Exception as e:
        db.session.rollback()
        flash('Ocurrió un error inesperado al eliminar el abono.', 'danger')
        current_app.logger.error(f"Error inesperado al eliminar abono {id}: {e}")
        
    return redirect(url_for('abonos.index'))


@abonos_bp.route('/generar_pdf/<int:abono_id>')
@login_required
@vendedor_cobrador_required
def generar_pdf(abono_id):
    abono = Abono.query.get_or_404(abono_id)
    
    # Verificar permisos para generar el PDF
    if not current_user.is_admin() and not puede_gestionar_venta_para_abono(abono.venta, current_user):
        if abono.cobrador_id != current_user.id:
            flash('No tiene permisos para generar este documento.', 'danger')
            return redirect(url_for('abonos.index'))
            
    try:
        pdf_output = generar_pdf_abono(abono)
        response = make_response(pdf_output)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=abono_{abono.id}.pdf'
        return response
    except Exception as e:
        current_app.logger.error(f"Error al generar PDF para abono {abono_id}: {e}")
        flash("No se pudo generar el PDF del abono.", "danger")
        return redirect(url_for('abonos.detalle', id=abono_id))


@abonos_bp.route('/get_abono_info/<int:abono_id>')
@login_required
@vendedor_cobrador_required
def get_abono_info(abono_id):
    """
    Endpoint para obtener datos de un abono (usado para la factura en el POS, por ejemplo)
    """
    abono = Abono.query.get(abono_id)
    if not abono:
        return jsonify({'error': 'Abono no encontrado'}), 404

    # Verificar permisos
    if not current_user.is_admin() and abono.cobrador_id != current_user.id:
         if not puede_gestionar_venta_para_abono(abono.venta, current_user):
            return jsonify({'error': 'No autorizado'}), 403

    return jsonify({
        'id': abono.id,
        'monto': str(abono.monto),
        'fecha': abono.fecha.strftime('%Y-%m-%d %H:%M:%S'),
        'venta_id': abono.venta_id,
        'cliente_nombre': abono.venta.cliente.nombre,
        'saldo_pendiente_venta': str(abono.venta.saldo_pendiente)
    })
    

@abonos_bp.route('/get_ventas_cliente/<int:cliente_id>')
@login_required
@vendedor_cobrador_required
def get_ventas_cliente(cliente_id):
    # Esta función parece ser un duplicado de /cargar-ventas.
    # Se podría unificar, pero se mantiene por retrocompatibilidad si algo más la usa.
    query = Venta.query.filter(
        Venta.cliente_id == cliente_id, 
        Venta.tipo == 'credito', 
        Venta.saldo_pendiente > 0
    )
    if not current_user.is_admin():
        query = query.filter(
            db.or_(
                Venta.usuario_actual_id == current_user.id,
                db.and_(
                    Venta.transferida == False,
                    Venta.vendedor_id == current_user.id
                )
            )
        )
    
    ventas = query.all()
    
    ventas_data = []
    for venta in ventas:
        ventas_data.append({
            'id': venta.id,
            'fecha': venta.fecha.strftime('%Y-%m-%d'),
            'saldo_pendiente': str(venta.saldo_pendiente)
        })
    return jsonify(ventas_data)