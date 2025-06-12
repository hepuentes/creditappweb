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
    
    if current_user.is_vendedor() and not current_user.is_admin():
        query = query.filter(
            db.or_(
                db.and_(
                    Venta.vendedor_id == current_user.id,
                    Venta.transferida == False
                ),
                db.and_(
                    Venta.transferida == True,
                    Venta.usuario_actual_id == current_user.id
                ),
                Abono.cobrador_id == current_user.id
            )
        )
    elif current_user.is_cobrador() and not current_user.is_admin():
        query = query.filter(
            db.or_(
                db.and_(
                    Venta.transferida == True,
                    Venta.usuario_actual_id == current_user.id
                ),
                Abono.cobrador_id == current_user.id,
                db.and_(
                    Venta.tipo == 'credito',
                    Venta.transferida == False
                )
            )
        )
    
    if busqueda:
        # Buscar por nombre de cliente asociado a la venta del abono
        query = query.join(Abono.venta).join(Venta.cliente).filter(Cliente.nombre.ilike(f"%{busqueda}%"))
    
    if desde_str:
        try:
            desde_dt = datetime.strptime(desde_str, '%Y-%m-%d')
            query = query.filter(Abono.fecha >= desde_dt)
        except ValueError:
            flash('Fecha "desde" inválida.', 'warning')
    
    if hasta_str:
        try:
            hasta_dt = datetime.strptime(hasta_str, '%Y-%m-%d')
            hasta_dt_fin_dia = datetime.combine(hasta_dt, datetime.max.time())
            query = query.filter(Abono.fecha <= hasta_dt_fin_dia)
        except ValueError:
            flash('Fecha "hasta" inválida.', 'warning')

    # Ordenar por fecha descendente
    abonos = query.order_by(Abono.fecha.desc()).all()
    
    # Calcular total de abonos
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
    cliente_id = request.args.get('cliente_id', type=int)
    venta_id = request.args.get('venta_id', type=int)
    
    form = AbonoForm()
    
    # Cargar cajas disponibles
    cajas = Caja.query.all()
    form.caja_id.choices = [(c.id, f"{c.nombre} ({c.tipo})") for c in cajas] if cajas else [(0, "No hay cajas disponibles")]
    
    # Obtener parámetros de URL
    
    # Cargar clientes según permisos y transferencias
    if current_user.is_vendedor() and not current_user.is_admin():
        clientes_query = Cliente.query.join(Venta).filter(
            Venta.tipo == 'credito',
            Venta.saldo_pendiente > 0,
            db.or_(
                # Ventas originales no transferidas
                db.and_(
                    Venta.vendedor_id == current_user.id,
                    Venta.transferida == False
                ),
                # Ventas transferidas a este usuario
                db.and_(
                    Venta.transferida == True,
                    Venta.usuario_actual_id == current_user.id
                )
            )
        ).distinct()
    elif current_user.is_cobrador() and not current_user.is_admin():
        clientes_query = Cliente.query.join(Venta).filter(
            Venta.tipo == 'credito',
            Venta.saldo_pendiente > 0,
            db.or_(
                # Ventas transferidas a este cobrador
                db.and_(
                    Venta.transferida == True,
                    Venta.usuario_actual_id == current_user.id
                ),
                # Todas las ventas a crédito (cobradores pueden cobrar cualquiera)
                Venta.transferida == False
            )
        ).distinct()
    else:
        # Admin ve todos los clientes con créditos pendientes
        clientes_query = Cliente.query.join(Venta).filter(
            Venta.tipo == 'credito',
            Venta.saldo_pendiente > 0
        ).distinct()
    
    clientes = clientes_query.order_by(Cliente.nombre).all()
    form.cliente_id.choices = [(-1, "Seleccionar cliente primero")] + [(c.id, c.nombre) for c in clientes]
    
    # Inicialmente, configurar opciones para ventas (esto se actualizará dinámicamente)
    form.venta_id.choices = [(-1, "Seleccione un cliente primero")]
    
    # Configuración si viene cliente_id o venta_id en la URL
    client_selected = False
    
    # Si tiene cliente_id, cargar sus ventas pendientes
    if cliente_id:
        current_app.logger.info(f"Preseleccionando cliente_id={cliente_id}")
        
        cliente = Cliente.query.get(cliente_id)
        if cliente:
            if any(c[0] == cliente_id for c in form.cliente_id.choices):
                form.cliente_id.data = cliente_id
                client_selected = True
                
                # MODIFICACIÓN: Cargar ventas considerando transferencias
                ventas_query = Venta.query.filter(
                    Venta.cliente_id == cliente_id,
                    Venta.tipo == 'credito', 
                    Venta.saldo_pendiente > 0
                )
                
                # Filtrar por permisos y transferencias
                if current_user.is_vendedor() and not current_user.is_admin():
                    ventas_query = ventas_query.filter(
                        db.or_(
                            # Ventas originales del vendedor
                            db.and_(
                                Venta.vendedor_id == current_user.id,
                                Venta.transferida == False
                            ),
                            # Ventas transferidas al vendedor
                            db.and_(
                                Venta.transferida == True,
                                Venta.usuario_actual_id == current_user.id
                            )
                        )
                    )
                elif current_user.is_cobrador() and not current_user.is_admin():
                    ventas_query = ventas_query.filter(
                        db.or_(
                            # Ventas transferidas al cobrador
                            db.and_(
                                Venta.transferida == True,
                                Venta.usuario_actual_id == current_user.id
                            ),
                            # Ventas sin transferir (cobradores pueden cobrar cualquiera)
                            Venta.transferida == False
                        )
                    )
                
                ventas_pendientes = ventas_query.all()
                
                if ventas_pendientes:
                    form.venta_id.choices = []
                    for v in ventas_pendientes:
                        # Mostrar información adicional sobre transferencias
                        etiqueta_extra = ""
                        if v.transferida:
                            etiqueta_extra = f" (Transferida - Gestor: {v.usuario_actual.nombre})"
                        
                        form.venta_id.choices.append((
                            v.id, 
                            f"Venta #{v.id} - {v.fecha.strftime('%d/%m/%Y')} - Saldo: ${v.saldo_pendiente:,.0f}{etiqueta_extra}"
                        ))
                else:
                    form.venta_id.choices = [(-1, "Este cliente no tiene ventas pendientes que puedas gestionar")]
            else:
                flash(f"El cliente con ID {cliente_id} no tiene ventas a crédito pendientes o no tienes permisos para gestionarlas", "warning")
    
        
    # Si tiene venta_id, preseleccionar la venta
    if venta_id:
        current_app.logger.info(f"Preseleccionando venta_id={venta_id}")
        
        venta = Venta.query.get(venta_id)
        if venta and venta.tipo == 'credito' and venta.saldo_pendiente > 0:
            # MODIFICACIÓN: Verificar si el usuario puede gestionar esta venta
            puede_gestionar = False
            
            if current_user.is_admin():
                puede_gestionar = True
            elif current_user.is_vendedor():
                # Vendedor puede gestionar si es original no transferida O transferida a él
                puede_gestionar = (
                    (venta.vendedor_id == current_user.id and not venta.transferida) or
                    (venta.transferida and venta.usuario_actual_id == current_user.id)
                )
            elif current_user.is_cobrador():
                # Cobrador puede gestionar si está transferida a él O no está transferida
                puede_gestionar = (
                    (venta.transferida and venta.usuario_actual_id == current_user.id) or
                    not venta.transferida
                )
            
            if puede_gestionar:
                if not client_selected:
                    cliente_id = venta.cliente_id
                    
                    if any(c[0] == cliente_id for c in form.cliente_id.choices):
                        form.cliente_id.data = cliente_id
                        client_selected = True
                    
                    # Cargar las ventas de este cliente
                    ventas_query = Venta.query.filter(
                        Venta.cliente_id == cliente_id,
                        Venta.tipo == 'credito', 
                        Venta.saldo_pendiente > 0
                    )
                    
                    if current_user.is_vendedor() and not current_user.is_admin():
                        ventas_query = ventas_query.filter(Venta.vendedor_id == current_user.id)
                    
                    ventas_pendientes = ventas_query.all()
                    
                    if ventas_pendientes:
                        form.venta_id.choices = [
                            (v.id, f"Venta #{v.id} - {v.fecha.strftime('%d/%m/%Y')} - Saldo: ${v.saldo_pendiente:,.0f}")
                            for v in ventas_pendientes
                        ]
            else:
                flash(f"No tienes permisos para realizar abonos a la venta #{venta_id}", "warning")
        else:
            if venta:
                flash(f"La venta #{venta_id} no es un crédito o no tiene saldo pendiente", "warning")
            else:
                flash(f"No se encontró la venta #{venta_id}", "warning")
    
    # VALIDACIÓN PERSONALIZADA EN LUGAR DE form.validate_on_submit()
    if request.method == 'POST':
        # Validar manualmente los campos críticos
        validation_errors = []
        
        # Validar cliente_id
        cliente_id_form = request.form.get('cliente_id')
        if not cliente_id_form or cliente_id_form == '-1':
            validation_errors.append("Debe seleccionar un cliente")
        else:
            try:
                cliente_id_form = int(cliente_id_form)
                cliente_form = Cliente.query.get(cliente_id_form)
                if not cliente_form:
                    validation_errors.append("Cliente no válido")
            except ValueError:
                validation_errors.append("Cliente no válido")
        
        # Validar venta_id MANUALMENTE (evitar el error "Not a valid choice")
        venta_id_form = request.form.get('venta_id')
        if not venta_id_form or venta_id_form == '-1':
            validation_errors.append("Debe seleccionar una venta")
        else:
            try:
                venta_id_form = int(venta_id_form)
                venta_form = Venta.query.get(venta_id_form)
                if not venta_form:
                    validation_errors.append("Venta no encontrada")
                elif venta_form.tipo != 'credito':
                    validation_errors.append("Solo se pueden registrar abonos para ventas a crédito")
                elif venta_form.saldo_pendiente <= 0:
                    validation_errors.append("Esta venta ya está pagada completamente")
                elif current_user.is_vendedor() and not current_user.is_admin():
                    if venta_form.vendedor_id != current_user.id:
                        validation_errors.append("No tienes permisos para abonar a esta venta")
            except ValueError:
                validation_errors.append("Venta no válida")
        
        # Validar monto
        monto_form = request.form.get('monto', '').strip()
        if not monto_form:
            validation_errors.append("Debe ingresar un monto")
        else:
            try:
                monto_form = monto_form.replace(',', '.')
                try:
                    monto_decimal = Decimal(monto_form)
                except InvalidOperation:
                    monto_str_limpio = monto_form.replace('.', '')
                    try:
                        monto_decimal = Decimal(monto_str_limpio)
                    except InvalidOperation:
                        validation_errors.append("Formato del monto no válido")
                        monto_decimal = None
                
                if monto_decimal is not None:
                    if monto_decimal <= 0:
                        validation_errors.append("El monto debe ser mayor a cero")
                    elif 'venta_form' in locals() and venta_form and monto_decimal > venta_form.saldo_pendiente:
                        validation_errors.append(f"El monto no puede ser mayor al saldo pendiente (${venta_form.saldo_pendiente:,.0f})")
            except Exception as e:
                validation_errors.append("Error al procesar el monto")
        
        # Validar caja_id
        caja_id_form = request.form.get('caja_id')
        if not caja_id_form:
            validation_errors.append("Debe seleccionar una caja")
        else:
            try:
                caja_id_form = int(caja_id_form)
                caja_form = Caja.query.get(caja_id_form)
                if not caja_form:
                    validation_errors.append("Caja no válida")
            except ValueError:
                validation_errors.append("Caja no válida")
        
        # Si hay errores de validación, mostrarlos
        if validation_errors:
            for error in validation_errors:
                flash(error, 'danger')
            current_app.logger.warning(f"Errores de validación personalizados: {validation_errors}")
            return render_template('abonos/crear.html', form=form, clientes=clientes)
        
        if all(validation_errors) == False:  # Si no hay errores de validación
            try:
                # Obtener la venta seleccionada
                venta_seleccionada = Venta.query.get(form.venta_id.data)
                
                # MODIFICACIÓN: Verificar permisos una vez más antes de crear
                puede_abonar = False
                if current_user.is_admin():
                    puede_abonar = True
                elif current_user.is_vendedor():
                    puede_abonar = (
                        (venta_seleccionada.vendedor_id == current_user.id and not venta_seleccionada.transferida) or
                        (venta_seleccionada.transferida and venta_seleccionada.usuario_actual_id == current_user.id)
                    )
                elif current_user.is_cobrador():
                    puede_abonar = (
                        (venta_seleccionada.transferida and venta_seleccionada.usuario_actual_id == current_user.id) or
                        not venta_seleccionada.transferida
                    )
                
                if not puede_abonar:
                    flash("No tienes permisos para realizar abonos a esta venta", "danger")
                    return render_template('abonos/crear.html', form=form)
                
                # Crear el abono
                nuevo_abono = Abono(
                    venta_id=form.venta_id.data,
                    monto=form.monto.data,
                    cobrador_id=current_user.id,  # Siempre el usuario actual
                    caja_id=form.caja_id.data,
                    notas=request.form.get('observaciones', '').strip()
                )
                
                current_app.logger.info(f"Intentando crear abono: venta_id={nuevo_abono.venta_id}, "
                                       f"monto={nuevo_abono.monto}, cobrador_id={nuevo_abono.cobrador_id}, "
                                       f"caja_id={nuevo_abono.caja_id}")
                
                db.session.add(nuevo_abono)
                db.session.flush()
                
                # Actualizar el saldo pendiente de la venta
                venta_seleccionada.saldo_pendiente = int(venta_seleccionada.saldo_pendiente) - int(nuevo_abono.monto)
                
                if venta_seleccionada.saldo_pendiente <= 0:
                    venta_seleccionada.estado = 'pagado'
                    venta_seleccionada.saldo_pendiente = 0
                
                # Registrar movimiento en caja
                movimiento = MovimientoCaja(
                    caja_id=nuevo_abono.caja_id,
                    tipo='entrada',
                    monto=nuevo_abono.monto,  # Usar int
                    descripcion=f'Abono a venta #{venta_seleccionada.id}'
                )
                db.session.add(movimiento)
                
                # Actualizar saldo de caja
                caja = Caja.query.get(nuevo_abono.caja_id)
                if caja:
                    caja.saldo_actual = int(caja.saldo_actual) + int(nuevo_abono.monto)
            
                # Calcular comisión (fuera del no_autoflush)
                try:
                    calcular_comision(float(nuevo_abono.monto), current_user.id, None, nuevo_abono.id)
                except Exception as e:
                    current_app.logger.error(f"Error al calcular comisión: {e}")
                
                # Commit de todos los cambios
                db.session.commit()
                
                # Al final, agregar información sobre transferencia en el mensaje de éxito
                mensaje_exito = f'Abono registrado exitosamente por ${nuevo_abono.monto:,.0f}'
                if venta_seleccionada.transferida:
                    mensaje_exito += f' (Venta transferida - gestionada por {venta_seleccionada.usuario_actual.nombre})'
                
                flash(mensaje_exito, 'success')
                
                return redirect(url_for('abonos.index'))
                
            except SQLAlchemyError as e:
                db.session.rollback()
                current_app.logger.error(f"Error de base de datos al registrar abono: {e}")
                flash('Error de base de datos al registrar el abono. Intente nuevamente.', 'danger')
            except Exception as e:
                db.session.rollback()
                current_app.logger.error(f"Error general al registrar abono: {e}")
                flash(f'Error al registrar el abono: {str(e)}', 'danger')
    
    return render_template('abonos/crear.html', form=form, clientes=clientes)

@abonos_bp.route('/cargar-ventas/<int:cliente_id>')
@login_required
@vendedor_cobrador_required
def cargar_ventas(cliente_id):
    try:
        # Consulta base para ventas a crédito con saldo pendiente
        query = Venta.query.filter(
            Venta.cliente_id == cliente_id,
            Venta.tipo == 'credito',
            Venta.saldo_pendiente > 0
        )
        
        # Si es vendedor, filtrar solo sus ventas
        if current_user.is_vendedor() and not current_user.is_admin():
            query = query.filter(Venta.vendedor_id == current_user.id)
        
        ventas = query.all()
        
        # Preparar datos para la respuesta JSON
        ventas_json = []
        if ventas:
            for v in ventas:
                ventas_json.append({
                    'id': int(v.id),
                    'texto': f"Venta #{v.id} - {v.fecha.strftime('%d/%m/%Y')} - Saldo: ${v.saldo_pendiente:,.0f}"
                })
        
        return jsonify(ventas_json)
    except Exception as e:
        current_app.logger.error(f"Error al cargar ventas para cliente {cliente_id}: {e}")
        return jsonify([]), 500

def puede_gestionar_venta_para_abono(venta, usuario):
    """
    Verifica si un usuario puede realizar abonos a una venta específica
    considerando las transferencias
    """
    if usuario.is_admin():
        return True
    
    if usuario.is_vendedor():
        # Vendedor puede abonar a sus ventas originales no transferidas
        # O a ventas transferidas a él
        return (
            (venta.vendedor_id == usuario.id and not venta.transferida) or
            (venta.transferida and venta.usuario_actual_id == usuario.id)
        )
    
    if usuario.is_cobrador():
        # Cobrador puede abonar a ventas transferidas a él
        # O a cualquier venta no transferida
        return (
            (venta.transferida and venta.usuario_actual_id == usuario.id) or
            not venta.transferida
        )
    
    return False

@abonos_bp.route('/<int:id>')
@login_required
@vendedor_cobrador_required
def detalle(id):
    abono = Abono.query.get_or_404(id)
    
    # MODIFICACIÓN: Verificar permisos considerando transferencias
    if current_user.is_vendedor() and not current_user.is_admin():
        puede_ver = False
        
        # Puede ver si es de una venta suya (original o transferida a él)
        if puede_gestionar_venta_para_abono(abono.venta, current_user):
            puede_ver = True
        
        # También puede ver si él hizo el abono
        if abono.cobrador_id == current_user.id:
            puede_ver = True
        
        if not puede_ver:
            flash('No tienes permiso para ver este abono', 'danger')
            return redirect(url_for('abonos.index'))
    
    # Obtener información de transferencias de la venta si aplica
    info_transferencia = None
    if abono.venta.transferida:
        info_transferencia = {
            'vendedor_original': abono.venta.vendedor_original.nombre,
            'usuario_actual': abono.venta.usuario_actual.nombre,
            'fecha_transferencia': abono.venta.fecha_transferencia
        }
    
    return render_template('abonos/detalle.html', 
                         abono=abono, 
                         info_transferencia=info_transferencia)

@abonos_bp.route('/editar/<int:id>', methods=['GET', 'POST'])
@login_required
@admin_required
def editar(id):
    abono = Abono.query.get_or_404(id)
    form = AbonoEditForm(obj=abono)
    
    # Cargar cajas disponibles
    cajas = Caja.query.all()
    form.caja_id.choices = [(c.id, f"{c.nombre} ({c.tipo})") for c in cajas] if cajas else [(0, "No hay cajas disponibles")]
    
    if form.validate_on_submit():
        try:
            # Guardar el monto original para el movimiento de caja
            monto_original = abono.monto
            caja_original_id = abono.caja_id
            
            # Actualizar abono
            form.populate_obj(abono)
            
            # Actualizar saldo de la venta
            venta = abono.venta
            
            # Revertir el abono original
            venta.saldo_pendiente += monto_original
            
            # Aplicar el nuevo abono
            venta.saldo_pendiente -= abono.monto
            
            if venta.saldo_pendiente <= 0:
                venta.estado = 'pagado'
                venta.saldo_pendiente = 0
            else:
                venta.estado = 'pendiente' # Asegurarse de que el estado sea pendiente si hay saldo
            
            # Actualizar movimientos de caja
            # Revertir movimiento original
            caja_original = Caja.query.get(caja_original_id)
            if caja_original:
                caja_original.saldo_actual -= monto_original
            
            # Crear nuevo movimiento o actualizar existente
            movimiento = MovimientoCaja.query.filter_by(abono_id=abono.id).first()
            if not movimiento:
                movimiento = MovimientoCaja(abono_id=abono.id)
                db.session.add(movimiento)
            
            movimiento.caja_id = abono.caja_id
            movimiento.tipo = 'entrada'
            movimiento.monto = abono.monto
            movimiento.descripcion = f'Abono a venta #{venta.id} (editado)'
            
            # Actualizar saldo de la nueva caja
            caja_nueva = Caja.query.get(abono.caja_id)
            if caja_nueva:
                caja_nueva.saldo_actual += abono.monto
            
            db.session.commit()
            flash('Abono actualizado exitosamente.', 'success')
            return redirect(url_for('abonos.index'))
        except SQLAlchemyError as e:
            db.session.rollback()
            flash(f'Error de base de datos al actualizar el abono: {e}' , 'danger')
        except Exception as e:
            db.session.rollback()
            flash(f'Error general al actualizar el abono: {str(e)}' , 'danger')
            
    return render_template('abonos/editar.html', form=form, abono=abono)

@abonos_bp.route('/eliminar/<int:id>', methods=['POST'])
@login_required
@admin_required
def eliminar(id):
    abono = Abono.query.get_or_404(id)
    try:
        # Revertir el saldo de la venta
        venta = abono.venta
        venta.saldo_pendiente += abono.monto
        venta.estado = 'pendiente' # La venta vuelve a estar pendiente
        
        # Revertir el movimiento de caja
        movimiento = MovimientoCaja.query.filter_by(abono_id=abono.id).first()
        if movimiento:
            caja = movimiento.caja
            if caja:
                caja.saldo_actual -= movimiento.monto
            db.session.delete(movimiento)
            
        db.session.delete(abono)
        db.session.commit()
        flash('Abono eliminado exitosamente.', 'success')
    except SQLAlchemyError as e:
        db.session.rollback()
        flash(f'Error de base de datos al eliminar el abono: {e}' , 'danger')
    except Exception as e:
        db.session.rollback()
        flash(f'Error general al eliminar el abono: {str(e)}' , 'danger')
        
    return redirect(url_for('abonos.index'))

@abonos_bp.route('/generar_pdf/<int:abono_id>')
@login_required
@vendedor_cobrador_required
def generar_pdf(abono_id):
    abono = Abono.query.get_or_404(abono_id)
    
    # Si es vendedor, verificar que el abono pertenezca a una de sus ventas
    if current_user.is_vendedor() and not current_user.is_admin():
        if abono.venta.vendedor_id != current_user.id:
            flash('No tienes permiso para generar PDF de este abono', 'danger')
            return redirect(url_for('abonos.index'))
            
    pdf_output = generar_pdf_abono(abono)
    response = make_response(pdf_output)
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename=abono_{abono.id}.pdf'
    return response

@abonos_bp.route('/get_abono_info/<int:abono_id>')
@login_required
@vendedor_cobrador_required
def get_abono_info(abono_id):
    abono = Abono.query.get(abono_id)
    if abono:
        return jsonify({
            'id': abono.id,
            'monto': str(abono.monto),
            'fecha': abono.fecha.strftime('%Y-%m-%d %H:%M:%S'),
            'venta_id': abono.venta_id,
            'cliente_nombre': abono.venta.cliente.nombre,
            'saldo_pendiente_venta': str(abono.venta.saldo_pendiente)
        })
    return jsonify({'error': 'Abono no encontrado'}), 404

@abonos_bp.route('/get_ventas_cliente/<int:cliente_id>')
@login_required
@vendedor_cobrador_required
def get_ventas_cliente(cliente_id):
    ventas = Venta.query.filter(Venta.cliente_id == cliente_id, Venta.tipo == 'credito', Venta.saldo_pendiente > 0).all()
    ventas_data = []
    for venta in ventas:
        ventas_data.append({
            'id': venta.id,
            'fecha': venta.fecha.strftime('%Y-%m-%d'),
            'saldo_pendiente': str(venta.saldo_pendiente)
        })
    return jsonify(ventas_data)