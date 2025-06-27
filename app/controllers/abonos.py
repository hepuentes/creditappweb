from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response, current_app, jsonify, abort
from flask_login import login_required, current_user
from sqlalchemy.exc import SQLAlchemyError
from app import db
from app.models import Abono, Cliente, Credito, CreditoVenta, Venta, Caja, MovimientoCaja
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
    query = Abono.query
    
    # Si es vendedor, filtrar solo sus propias ventas/abonos
    if current_user.is_vendedor():
        query = query.join(Abono.venta).filter(Venta.vendedor_id == current_user.id)
    
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
    form = AbonoForm()
    
    # Cargar cajas disponibles
    cajas = Caja.query.all()
    form.caja_id.choices = [(c.id, f"{c.nombre} ({c.tipo})") for c in cajas] if cajas else [(0, "No hay cajas disponibles")]
    
    # Obtener parámetros de URL
    cliente_id = request.args.get('cliente_id', type=int)
    venta_id = request.args.get('venta_id', type=int)
    
    # Modificar la consulta para vendedores - solo mostrar sus clientes
    if current_user.is_vendedor() and not current_user.is_admin():
        clientes_query = db.session.query(Cliente).join(Venta).filter(
            Venta.tipo == 'credito',
            Venta.saldo_pendiente > 0,
            Venta.vendedor_id == current_user.id
        ).distinct().order_by(Cliente.nombre)
    else:
        clientes_query = db.session.query(Cliente).join(Venta).filter(
            Venta.tipo == 'credito',
            Venta.saldo_pendiente > 0
        ).distinct().order_by(Cliente.nombre)
    
    clientes = clientes_query.all()

    # Configurar opciones para el select de clientes
    if clientes:
        form.cliente_id.choices = [(c.id, f"{c.nombre} - {c.cedula}") for c in clientes]
    else:
        form.cliente_id.choices = [(-1, "No hay clientes con créditos pendientes")]
    
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
                
                # Cargar las ventas de este cliente (filtrar por vendedor si es necesario)
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
                    form.venta_id.choices = [(-1, "Este cliente no tiene ventas pendientes")]
            else:
                flash(f"El cliente con ID {cliente_id} no tiene ventas a crédito pendientes o no pertenece a sus ventas", "warning")
    
    # Si tiene venta_id, preseleccionar la venta
    if venta_id:
        current_app.logger.info(f"Preseleccionando venta_id={venta_id}")
        
        venta = Venta.query.get(venta_id)
        if venta and venta.tipo == 'credito' and venta.saldo_pendiente > 0:
            # Verificar si el vendedor puede acceder a esta venta
            if current_user.is_vendedor() and not current_user.is_admin():
                if venta.vendedor_id != current_user.id:
                    flash("No tienes permisos para abonar a esta venta", "danger")
                    return redirect(url_for('abonos.index'))
            
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
            
            # Seleccionar la venta en el dropdown
            if any(v[0] == venta_id for v in form.venta_id.choices):
                form.venta_id.data = venta_id
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
        
        # Si llegamos aquí, la validación pasó - procesar el abono
        try:
            # SOLUCIÓN: Usar session.no_autoflush para evitar flush prematuro
            with db.session.no_autoflush:
                # Usar las variables ya validadas y CONVERTIR A INT para consistencia
                venta = venta_form
                monto_int = int(monto_decimal)  # Convertir a entero (representando centavos si es necesario)
                
                # Crear el abono
                abono = Abono(
                    venta_id=venta.id,
                    monto=monto_int,  # Usar int para consistencia con otros campos monetarios
                    fecha=datetime.utcnow(),
                    cobrador_id=current_user.id,
                    caja_id=caja_id_form,
                    notas=request.form.get('notas', '').strip()
                )
                
                current_app.logger.info(f"Intentando crear abono: venta_id={abono.venta_id}, "
                                       f"monto={monto_int}, cobrador_id={abono.cobrador_id}, "
                                       f"caja_id={abono.caja_id}")
                
                db.session.add(abono)
                db.session.flush()
                
                # Actualizar el saldo pendiente de la venta
                venta.saldo_pendiente = int(venta.saldo_pendiente) - monto_int
                
                if venta.saldo_pendiente <= 0:
                    venta.estado = 'pagado'
                    venta.saldo_pendiente = 0
                
                # Registrar movimiento en caja
                movimiento = MovimientoCaja(
                    caja_id=caja_id_form,
                    tipo='entrada',
                    monto=monto_int,  # Usar int
                    descripcion=f'Abono a venta #{venta.id}',
                    abono_id=abono.id
                )
                db.session.add(movimiento)
                
                # Actualizar saldo de caja
                caja = Caja.query.get(caja_id_form)
                if caja:
                    caja.saldo_actual = int(caja.saldo_actual) + monto_int
            
            # Calcular comisión (fuera del no_autoflush)
            try:
                calcular_comision(float(monto_int), current_user.id, None, abono.id)
            except Exception as e:
                current_app.logger.error(f"Error al calcular comisión: {e}")
            
            # Commit de todos los cambios
            db.session.commit()
            
            monto_formateado = f"${monto_int:,.0f}"
            flash(f'Abono de {monto_formateado} registrado exitosamente', 'success')
            
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
        else:
            ventas_json.append({
                'id': -1,
                'texto': "Este cliente no tiene ventas a crédito pendientes"
            })
        
        return jsonify(ventas_json)
    except Exception as e:
        current_app.logger.error(f"Error al cargar ventas: {e}")
        return jsonify([{"id": -1, "texto": "Error al cargar ventas"}])

@abonos_bp.route('/<int:id>')
@login_required
@vendedor_cobrador_required  # Cambiado de @cobrador_required
def detalle(id):
    abono = Abono.query.get_or_404(id)
    
    # Si es vendedor, verificar que el abono pertenezca a una venta suya
    if current_user.is_vendedor() and not current_user.is_admin():
        if abono.venta and abono.venta.vendedor_id != current_user.id:
            flash('No tienes permisos para ver este abono', 'danger')
            return redirect(url_for('dashboard.index'))
    
    return render_template('abonos/detalle.html', abono=abono)

@abonos_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@admin_required
def editar(id):
    abono = Abono.query.get_or_404(id)
    form = AbonoEditForm(abono=abono)
    
    # Cargar cajas disponibles
    cajas = Caja.query.all()
    form.caja_id.choices = [(c.id, f"{c.nombre} ({c.tipo})") for c in cajas]
    
    # Precargar datos del abono
    if request.method == 'GET':
        form.monto.data = str(int(abono.monto))  # Convertir a int para display
        form.caja_id.data = abono.caja_id
        form.notas.data = abono.notas
        
        # Configurar cliente y venta
        if abono.venta:
            cliente = abono.venta.cliente
            venta = abono.venta
    
    if form.validate_on_submit():
        try:
            with db.session.no_autoflush:
                # Guardar valores originales para cálculos
                monto_original = int(abono.monto)
                caja_original_id = abono.caja_id
                
                # Validar nuevo monto
                nuevo_monto_str = request.form.get('monto', '').strip().replace(',', '.')
                try:
                    nuevo_monto = int(float(nuevo_monto_str))  # Convertir a int
                except ValueError:
                    flash('Formato del monto no válido', 'danger')
                    return render_template('abonos/editar.html', form=form, abono=abono)
                
                if nuevo_monto <= 0:
                    flash('El monto debe ser mayor a cero', 'danger')
                    return render_template('abonos/editar.html', form=form, abono=abono)
                
                # Validar que el nuevo monto no exceda el saldo disponible
                venta = abono.venta
                saldo_disponible = int(venta.saldo_pendiente) + monto_original
                
                if nuevo_monto > saldo_disponible:
                    flash(f'El monto no puede ser mayor al saldo disponible (${saldo_disponible:,.0f})', 'danger')
                    return render_template('abonos/editar.html', form=form, abono=abono)
                
                # Calcular diferencia de montos
                diferencia_monto = nuevo_monto - monto_original
                
                # Actualizar el abono
                abono.monto = nuevo_monto
                abono.caja_id = form.caja_id.data
                abono.notas = form.notas.data
                
                # Actualizar saldo de la venta
                venta.saldo_pendiente = int(venta.saldo_pendiente) - diferencia_monto
                
                if venta.saldo_pendiente <= 0:
                    venta.estado = 'pagado'
                    venta.saldo_pendiente = 0
                else:
                    venta.estado = 'pendiente'
                
                # Actualizar movimientos de caja
                movimientos_existentes = MovimientoCaja.query.filter_by(abono_id=abono.id).all()
                
                # Si cambió la caja o el monto, actualizar movimientos
                if caja_original_id != form.caja_id.data or diferencia_monto != 0:
                    # Eliminar movimientos existentes
                    for mov in movimientos_existentes:
                        # Revertir el movimiento en la caja original
                        caja_original = Caja.query.get(mov.caja_id)
                        if caja_original:
                            caja_original.saldo_actual = int(caja_original.saldo_actual) - int(mov.monto)
                        db.session.delete(mov)
                    
                    # Crear nuevo movimiento en la caja seleccionada
                    nuevo_movimiento = MovimientoCaja(
                        caja_id=form.caja_id.data,
                        tipo='entrada',
                        monto=nuevo_monto,
                        descripcion=f'Abono a venta #{venta.id} (editado)',
                        abono_id=abono.id
                    )
                    db.session.add(nuevo_movimiento)
                    
                    # Actualizar saldo de la nueva caja
                    nueva_caja = Caja.query.get(form.caja_id.data)
                    if nueva_caja:
                        nueva_caja.saldo_actual = int(nueva_caja.saldo_actual) + nuevo_monto
            
            db.session.commit()
            
            flash(f'Abono #{abono.id} editado exitosamente. Nuevo monto: ${nuevo_monto:,.0f}', 'success')
            return redirect(url_for('abonos.detalle', id=abono.id))
            
        except SQLAlchemyError as e:
            db.session.rollback()
            current_app.logger.error(f"Error de base de datos al editar abono {id}: {e}")
            flash('Error de base de datos al editar el abono. Intente nuevamente.', 'danger')
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error general al editar abono {id}: {e}")
            flash(f'Error al editar el abono: {str(e)}', 'danger')
    
    return render_template('abonos/editar.html', form=form, abono=abono)

@abonos_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def eliminar(id):
    abono = Abono.query.get_or_404(id)
    
    try:
        with db.session.no_autoflush:
            # Guardar información para el mensaje
            monto_abono = int(abono.monto)
            venta_id = abono.venta_id
            
            # Restaurar saldo pendiente de la venta
            if abono.venta:
                venta = abono.venta
                venta.saldo_pendiente = int(venta.saldo_pendiente) + monto_abono
                venta.estado = 'pendiente'  # Cambiar estado a pendiente
            
            # Eliminar movimientos de caja asociados y revertir saldos
            movimientos = MovimientoCaja.query.filter_by(abono_id=abono.id).all()
            for movimiento in movimientos:
                # Revertir el saldo de la caja
                caja = Caja.query.get(movimiento.caja_id)
                if caja:
                    caja.saldo_actual = int(caja.saldo_actual) - int(movimiento.monto)
                
                db.session.delete(movimiento)
            
            # Eliminar comisiones asociadas (si existen)
            from app.models import Comision
            comisiones = Comision.query.filter_by(abono_id=abono.id).all()
            for comision in comisiones:
                db.session.delete(comision)
            
            # Eliminar el abono
            db.session.delete(abono)
        
        db.session.commit()
        
        flash(f'Abono de ${monto_abono:,.0f} eliminado exitosamente. Saldo de venta #{venta_id} restaurado.', 'success')
        
    except SQLAlchemyError as e:
        db.session.rollback()
        current_app.logger.error(f"Error de base de datos al eliminar abono {id}: {e}")
        flash('Error de base de datos al eliminar el abono. Intente nuevamente.', 'danger')
        return redirect(url_for('abonos.detalle', id=id))
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error general al eliminar abono {id}: {e}")
        flash(f'Error al eliminar el abono: {str(e)}', 'danger')
        return redirect(url_for('abonos.detalle', id=id))
    
    return redirect(url_for('abonos.index'))

@abonos_bp.route('/<int:id>/pdf')
@login_required
@vendedor_cobrador_required  # Cambiado para permitir vendedores
def pdf(id):
    abono = Abono.query.get_or_404(id)
    
    # Si es vendedor, verificar que el abono pertenezca a una venta suya
    if current_user.is_vendedor() and not current_user.is_admin():
        if abono.venta and abono.venta.vendedor_id != current_user.id:
            flash('No tienes permisos para ver este PDF', 'danger')
            return redirect(url_for('dashboard.index'))
    
    try:
        pdf_bytes = generar_pdf_abono(abono)
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=abono_{abono.id}.pdf'
        return response
    except Exception as e:
        current_app.logger.error(f"Error generando PDF: {e}")
        flash(f"Error generando el PDF: {str(e)}", "danger")
        return redirect(url_for('abonos.detalle', id=id))

@abonos_bp.route('/<int:id>/share')
@login_required
@vendedor_cobrador_required
def compartir(id):
    try:
        abono = Abono.query.get_or_404(id)
        
        # Verificar permisos si es vendedor
        if current_user.is_vendedor() and not current_user.is_admin():
            if abono.venta and abono.venta.vendedor_id != current_user.id:
                flash('No tienes permisos para compartir este abono', 'danger')
                return redirect(url_for('abonos.index'))
        
        # Redirigir directamente a la página de compartir sin usar sesión
        return redirect(url_for('public.share_page', tipo='abono', id=id))
        
    except Exception as e:
        current_app.logger.error(f"Error al compartir abono {id}: {e}")
        flash('Error al generar documento para compartir', 'danger')
        return redirect(url_for('abonos.detalle', id=id))