from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify, current_app, make_response
from flask_login import login_required, current_user
from app import db
from app.models import (Venta, Cliente, Producto, DetalleVenta, Usuario, MovimientoCaja, 
                       TransferenciaVenta, Comision, Caja)  
from app.forms import VentaForm
from app.decorators import admin_required, vendedor_extended_required, vendedor_required
from app.utils import calcular_comision, format_currency, registrar_movimiento_caja
from app.pdf.venta import generar_pdf_venta
from datetime import datetime
import json
import traceback

ventas_bp = Blueprint('ventas', __name__, url_prefix='/ventas')

@ventas_bp.route('/')
@login_required
@vendedor_extended_required
def index():
    # Filtros de búsqueda
    busqueda = request.args.get('busqueda', '')
    tipo = request.args.get('tipo', '')
    estado = request.args.get('estado', '')
    transferida_str = request.args.get('transferida')

    # Query base
    query = Venta.query.join(Cliente)
    
    # MODIFICACIÓN: Filtrar según el rol y transferencias
    if current_user.is_vendedor() and not current_user.is_admin():
        # Vendedores ven sus ventas originales Y las que tienen asignadas por transferencia
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
                db.and_(
                    Venta.vendedor_original_id == current_user.id,
                    Venta.transferida == True
                )
            )
        )
    
    # Aplicar filtros de búsqueda
    if busqueda:
        query = query.filter(Cliente.nombre.ilike(f'%{busqueda}%'))
    if tipo:
        query = query.filter(Venta.tipo == tipo)
    if estado:
        query = query.filter(Venta.estado == estado)
    if transferida_str is not None and transferida_str != '':
        query = query.filter(Venta.transferida == (transferida_str == '1'))

    # Paginación
    page = request.args.get('page', 1, type=int)
    per_page = 20
    
    ventas_paginadas = query.order_by(Venta.fecha.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )
    
    return render_template('ventas/index.html', 
                         ventas=ventas_paginadas, 
                         busqueda=busqueda,
                         tipo=tipo, 
                         estado=estado)

@ventas_bp.route('/crear', methods=['GET', 'POST'])
@login_required
@vendedor_required
def crear():
    # Inicializar el formulario
    form = VentaForm()
    
    # Obtener cliente_id de la URL si existe
    cliente_id_param = request.args.get('cliente_id', type=int)
    
    # Cargar opciones para los selectores
    clientes = Cliente.query.order_by(Cliente.nombre).all()
    form.cliente.choices = [(c.id, f"{c.nombre} - {c.cedula}") for c in clientes]
    
    # Si hay un cliente_id en la URL, preseleccionarlo
    if cliente_id_param and request.method == 'GET':
        cliente = Cliente.query.get(cliente_id_param)
        if cliente:
            form.cliente.data = cliente.id
    
    # Cargar opciones para los selectores de caja
    cajas = Caja.query.all()
    form.caja.choices = [(c.id, c.nombre) for c in cajas]
    
    # Obtener productos disponibles para la vista
    productos_disponibles = Producto.query.filter(Producto.stock > 0).order_by(Producto.nombre).all()
    
    # Log para depuración
    if request.method == 'POST':
        current_app.logger.info(f"Datos del formulario recibidos: {request.form}")
        
    # Procesar el formulario cuando se envía
    if form.validate_on_submit():
        current_app.logger.info("Formulario validado correctamente")
        
        # Obtener productos del campo JSON
        productos_json = request.form.get('productos_json', '[]')
        current_app.logger.info(f"Productos JSON: {productos_json}")
        
        try:
            # Decodificar JSON de productos
            productos_seleccionados = json.loads(productos_json)
            
            # Verificar si hay productos seleccionados
            if not productos_seleccionados:
                flash('No se seleccionaron productos para la venta.', 'danger')
                return render_template('ventas/crear.html', form=form, productos=productos_disponibles)
            
            current_app.logger.info(f"Productos decodificados: {productos_seleccionados}")
            
            # Crear nueva venta
            nueva_venta = Venta(
                cliente_id=form.cliente.data,
                vendedor_id=current_user.id,
                tipo=form.tipo.data,
                fecha=datetime.utcnow(),
                total=0,  # Se calculará después
                saldo_pendiente=0  # Se calculará después
            )
            
            # Establecer estado según tipo de venta
            if form.tipo.data == 'contado':
                nueva_venta.estado = 'pagado'
            else:
                nueva_venta.estado = 'pendiente'
            
            db.session.add(nueva_venta)
            db.session.flush()  # Para obtener el ID antes del commit
            
            # Procesar los productos seleccionados
            total_venta_calculado = 0
            
            for item in productos_seleccionados:
                producto_id = int(item.get('id', 0))
                cantidad = int(item.get('cantidad', 0))
                precio_venta = float(item.get('precio_venta', 0))
                
                # Verificar stock disponible
                producto_db = Producto.query.get(producto_id)
                if not producto_db:
                    flash(f"Producto no encontrado.", 'danger')
                    db.session.rollback()
                    return render_template('ventas/crear.html', form=form, productos=productos_disponibles)
                
                if producto_db.stock < cantidad:
                    flash(f"Stock insuficiente para {producto_db.nombre}. Disponible: {producto_db.stock}", 'danger')
                    db.session.rollback()
                    return render_template('ventas/crear.html', form=form, productos=productos_disponibles)
                
                # Crear detalle de venta
                subtotal = cantidad * precio_venta
                detalle = DetalleVenta(
                    venta_id=nueva_venta.id,
                    producto_id=producto_id,
                    cantidad=cantidad,
                    precio_unitario=precio_venta,
                    subtotal=subtotal
                )
                db.session.add(detalle)
                
                # Actualizar stock
                producto_db.stock -= cantidad
                
                # Sumar al total
                total_venta_calculado += subtotal
            
            # Actualizar total y saldo pendiente
            nueva_venta.total = total_venta_calculado
            
            if form.tipo.data == 'credito':
                nueva_venta.saldo_pendiente = total_venta_calculado
            else:  # contado
                nueva_venta.saldo_pendiente = 0
                
                # Registrar movimiento en caja para ventas de contado
                try:
                    registrar_movimiento_caja(
                        caja_id=form.caja.data,
                        tipo='entrada',
                        monto=total_venta_calculado,
                        concepto=f"Venta de contado #{nueva_venta.id}",
                        venta_id=nueva_venta.id
                    )
                except Exception as e:
                    current_app.logger.error(f"Error al registrar movimiento de caja: {e}")
                    # Continuar a pesar del error en la caja
            
            # Calcular comisión por la venta
            try:
                calcular_comision(total_venta_calculado, current_user.id, nueva_venta.id)
            except Exception as e:
                current_app.logger.error(f"Error al calcular comisión: {e}")
                # Continuar a pesar del error en la comisión
            
            # Confirmar cambios
            db.session.commit()
            flash(f'Venta #{nueva_venta.id} creada exitosamente!', 'success')
            
            # Redireccionar al detalle de la venta en lugar de la lista
            return redirect(url_for('ventas.detalle', id=nueva_venta.id))
            
        except json.JSONDecodeError as e:
            current_app.logger.error(f"Error al decodificar JSON: {e}")
            flash('Error en el formato de productos seleccionados.', 'danger')
            return render_template('ventas/crear.html', form=form, productos=productos_disponibles)
        except Exception as e:
            db.session.rollback()
            current_app.logger.error(f"Error al crear venta: {e}")
            current_app.logger.error(traceback.format_exc())
            flash(f'Error al crear la venta: {str(e)}', 'danger')
    elif request.method == 'POST':
        # Si el formulario no se validó, mostrar errores
        current_app.logger.warning(f"Errores de validación: {form.errors}")
        flash('Por favor corrija los errores en el formulario.', 'warning')
    
    return render_template('ventas/crear.html', form=form, productos=productos_disponibles)

@ventas_bp.route('/<int:id>')
@login_required
def detalle(id):
    venta = Venta.query.get_or_404(id)
    
    # MODIFICACIÓN: Verificar permisos considerando transferencias
    if current_user.is_vendedor() and not current_user.is_admin():
        puede_ver = False
        
        # Puede ver si es el vendedor original
        if venta.vendedor_id == current_user.id:
            puede_ver = True
        
        # Puede ver si es el usuario actual de una venta transferida
        if venta.transferida and venta.usuario_actual_id == current_user.id:
            puede_ver = True
        
        # Puede ver si es el vendedor original de una venta transferida
        if venta.transferida and venta.vendedor_original_id == current_user.id:
            puede_ver = True
        
        if not puede_ver:
            flash('No tienes permiso para ver esta venta', 'danger')
            return redirect(url_for('ventas.index'))
    
    # MODIFICACIÓN: Obtener historial de transferencias si existe
    transferencias = []
    if venta.transferida:
        transferencias = TransferenciaVenta.query.filter_by(
            venta_id=venta.id
        ).order_by(TransferenciaVenta.fecha.desc()).all()
    
    return render_template('ventas/detalle.html', 
                         venta=venta, 
                         transferencias=transferencias)

# Ver transferencias de una venta desde el detalle
@ventas_bp.route('/<int:id>/transferencias')
@login_required
def ver_transferencias(id):
    """Muestra las transferencias de una venta específica"""
    venta = Venta.query.get_or_404(id)
    
    # Verificar permisos (similar a detalle)
    if current_user.is_vendedor() and not current_user.is_admin():
        puede_ver = (venta.vendedor_id == current_user.id or 
                     (venta.transferida and venta.usuario_actual_id == current_user.id) or
                     (venta.transferida and venta.vendedor_original_id == current_user.id))
        
        if not puede_ver:
            flash('No tienes permiso para ver esta información', 'danger')
            return redirect(url_for('ventas.index'))
    
    return redirect(url_for('transferencias.historial_venta', venta_id=id))

# FUNCIÓN AUXILIAR: Verificar si usuario puede gestionar venta
def puede_gestionar_venta(venta, usuario):
    """
    Verifica si un usuario puede realizar acciones sobre una venta 
    (como eliminar, editar, etc.)
    """
    if usuario.is_admin():
        return True
    
    if venta.transferida:
        return venta.usuario_actual_id == usuario.id
    else:
        return venta.vendedor_id == usuario.id

@ventas_bp.route('/<int:id>/pdf')
@login_required
def pdf(id):
    venta = Venta.query.get_or_404(id)
    try:
        pdf_bytes = generar_pdf_venta(venta)
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=venta_{venta.id}.pdf'
        return response
    except Exception as e:
        flash(f"Error generando el PDF: {str(e)}", "danger")
        return redirect(url_for('ventas.detalle', id=id))

@ventas_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required  # Solo admin puede eliminar ventas
def eliminar(id):
    venta = Venta.query.get_or_404(id)
    try:
        # Verificar que no haya abonos si es crédito
        if venta.tipo == 'credito' and venta.abonos:
            flash('No se puede eliminar una venta a crédito que tiene abonos registrados.', 'danger')
            return redirect(url_for('ventas.detalle', id=id))
        
        # Verificar que no esté transferida o solo permita admin
        if venta.transferida and not current_user.is_admin():
            flash('Solo los administradores pueden eliminar ventas transferidas.', 'danger')
            return redirect(url_for('ventas.detalle', id=id))
        
        # Restaurar stock de productos
        for detalle in venta.detalles:
            producto = Producto.query.get(detalle.producto_id)
            if producto:
                producto.stock += detalle.cantidad
        
        # Eliminar movimientos de caja asociados
        MovimientoCaja.query.filter_by(venta_id=id).delete()
        
        # Eliminar transferencias asociadas
        TransferenciaVenta.query.filter_by(venta_id=id).delete()
        
        # Eliminar comisiones asociadas
        Comision.query.filter_by(venta_id=id).delete()
        
        # Eliminar detalles y luego la venta
        DetalleVenta.query.filter_by(venta_id=id).delete()
        
        db.session.delete(venta)
        db.session.commit()
        flash(f'Venta #{id} eliminada exitosamente y stock restaurado.', 'success')
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error eliminando venta {id}: {e}")
        flash(f'Error al eliminar la venta: {str(e)}', 'danger')
    
    return redirect(url_for('ventas.index'))

@ventas_bp.route('/<int:id>/share')
@login_required
def compartir(id):
    try:
        venta = Venta.query.get_or_404(id)
        
        # Verificar permisos considerando transferencias
        if current_user.is_vendedor() and not current_user.is_admin():
            puede_compartir = (venta.vendedor_id == current_user.id or 
                             (venta.transferida and venta.usuario_actual_id == current_user.id))
            
            if not puede_compartir:
                flash('No tienes permisos para compartir esta venta', 'danger')
                return redirect(url_for('ventas.index'))
        
        # Redirigir directamente a la página de compartir sin usar sesión
        return redirect(url_for('public.share_page', tipo='venta', id=id))
        
    except Exception as e:
        current_app.logger.error(f"Error al compartir venta {id}: {e}")
        flash('Error al generar documento para compartir', 'danger')
        return redirect(url_for('ventas.detalle', id=id))

# FUNCIÓN: API para obtener información de transferencia de una venta
@ventas_bp.route('/api/<int:id>/info-transferencia')
@login_required
def api_info_transferencia(id):
    """API endpoint para obtener información de transferencia de una venta"""
    try:
        venta = Venta.query.get_or_404(id)
        
        info = {
            'id': venta.id,
            'transferida': venta.transferida,
            'vendedor_original': None,
            'usuario_actual': None,
            'puede_transferir': current_user.is_admin(),
            'puede_gestionar': puede_gestionar_venta(venta, current_user)
        }
        
        if venta.transferida:
            info['vendedor_original'] = {
                'id': venta.vendedor_original.id,
                'nombre': venta.vendedor_original.nombre,
                'rol': venta.vendedor_original.rol
            }
            info['usuario_actual'] = {
                'id': venta.usuario_actual.id,
                'nombre': venta.usuario_actual.nombre,
                'rol': venta.usuario_actual.rol
            }
        
        return jsonify(info)
        
    except Exception as e:
        current_app.logger.error(f"Error en API info transferencia: {e}")
        return jsonify({'error': str(e)}), 500