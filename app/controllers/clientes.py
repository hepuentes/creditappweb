from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response
from flask_login import login_required, current_user
from app import db
from app.models import Cliente, Venta, Credito, Abono
from app.forms import ClienteForm
from app.decorators import (
    vendedor_required,
    cobrador_required,
    admin_required
)
from app.pdf.cliente import generar_pdf_historial

clientes_bp = Blueprint('clientes', __name__, url_prefix='/clientes')

@clientes_bp.route('/')
@login_required
def index():
    busqueda = request.args.get('busqueda', '')
    query = Cliente.query
    
    # Filtrar por vendedor si es vendedor y no admin
    if current_user.is_vendedor() and not current_user.is_admin():
        # Obtener IDs de clientes que tienen ventas hechas por este vendedor
        clientes_ids = db.session.query(Venta.cliente_id).filter_by(vendedor_id=current_user.id).distinct()
        query = query.filter(Cliente.id.in_(clientes_ids))
    
    if busqueda:
        query = query.filter(Cliente.nombre.ilike(f"%{busqueda}%") | Cliente.cedula.ilike(f"%{busqueda}%"))
    
    clientes = query.all()
    
    # Determinar si el usuario actual solo puede consultar
    solo_consulta = current_user.is_vendedor() and not current_user.is_admin()
    
    return render_template('clientes/index.html', clientes=clientes, busqueda=busqueda, solo_consulta=solo_consulta)

@clientes_bp.route('/crear', methods=['GET', 'POST'])
@login_required
@vendedor_required
def crear():
    form = ClienteForm()
    if form.validate_on_submit():
        # Verificar si la cédula ya existe
        cliente_existente = Cliente.query.filter_by(cedula=form.cedula.data).first()
        if cliente_existente:
            # Para vendedores, verificar si pueden acceder a ese cliente
            if current_user.is_vendedor() and not current_user.is_admin():
                # Verificar si este vendedor ya ha hecho ventas a este cliente
                venta_existente = Venta.query.filter_by(
                    cliente_id=cliente_existente.id,
                    vendedor_id=current_user.id
                ).first()
                
                if venta_existente:
                    # El vendedor ya tiene ventas con este cliente
                    flash(f'Ya existe un cliente con la cédula {form.cedula.data}. '
                          f'Cliente: {cliente_existente.nombre}. '
                          f'Puede encontrarlo en su lista de clientes.', 'warning')
                    return redirect(url_for('clientes.detalle', id=cliente_existente.id))
                else:
                    # El cliente existe pero este vendedor no le ha vendido
                    flash(f'Ya existe un cliente con la cédula {form.cedula.data}. '
                          f'Cliente: {cliente_existente.nombre}. '
                          f'Para hacer una venta a este cliente, use el botón "Nueva Venta" a continuación.', 'info')
                    return redirect(url_for('ventas.crear', cliente_id=cliente_existente.id))
            else:
                # Para administradores
                flash(f'Ya existe un cliente con la cédula {form.cedula.data}. '
                      f'Cliente: {cliente_existente.nombre}.', 'warning')
                return redirect(url_for('clientes.detalle', id=cliente_existente.id))
        
        # Si no existe, crear el nuevo cliente
        cliente = Cliente(
            nombre=form.nombre.data,
            cedula=form.cedula.data,
            telefono=form.telefono.data,
            email=form.email.data,
            direccion=form.direccion.data
        )
        db.session.add(cliente)
        db.session.commit()
        flash('Cliente creado exitosamente', 'success')
        
        # Redirigir al detalle del cliente recién creado en lugar de la lista
        return redirect(url_for('clientes.detalle', id=cliente.id))
    return render_template('clientes/crear.html', form=form, titulo='Nuevo Cliente')

@clientes_bp.route('/<int:id>/editar', methods=['GET', 'POST'])
@login_required
@vendedor_required
def editar(id):
    cliente = Cliente.query.get_or_404(id)
    form = ClienteForm(obj=cliente)
    if form.validate_on_submit():
        # Verificar si la nueva cédula ya existe en otro cliente
        if form.cedula.data != cliente.cedula:
            cliente_existente = Cliente.query.filter_by(cedula=form.cedula.data).first()
            if cliente_existente:
                flash(f'Ya existe otro cliente con la cédula {form.cedula.data}. '
                      f'Cliente: {cliente_existente.nombre}.', 'danger')
                return render_template('clientes/crear.html', form=form, titulo='Editar Cliente')
        
        form.populate_obj(cliente)
        db.session.commit()
        flash('Cliente actualizado exitosamente', 'success')
        return redirect(url_for('clientes.detalle', id=cliente.id))
    return render_template('clientes/crear.html', form=form, titulo='Editar Cliente')

@clientes_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
@vendedor_required
def eliminar(id):
    cliente = Cliente.query.get_or_404(id)
    try:
        db.session.delete(cliente)
        db.session.commit()
        flash('Cliente eliminado exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el cliente: {str(e)}', 'danger')
    return redirect(url_for('clientes.index'))

@clientes_bp.route('/<int:id>')
@login_required
def detalle(id):
    cliente = Cliente.query.get_or_404(id)
    
    # Si es una petición para el modal
    if request.args.get('modal') == 'true':
        return render_template('clientes/detalle_modal.html', cliente=cliente)
    
    # Vista normal
    ventas = cliente.ventas
    creditos = cliente.creditos
    
    # Recopilar abonos a través de las ventas
    abonos_cliente = []
    for venta in ventas:
        if hasattr(venta, 'abonos') and venta.abonos:
            abonos_cliente.extend(venta.abonos)
    
    # También obtener abonos a través de creditos directos
    for credito in creditos:
        if hasattr(credito, 'abonos') and credito.abonos:
            abonos_cliente.extend(credito.abonos)
    
    # Ordenar abonos por fecha (más recientes primero)
    abonos_cliente.sort(key=lambda x: x.fecha, reverse=True)
    
    # Determinar si viene de la sección de créditos
    from_creditos = request.referrer and 'creditos' in request.referrer
    
    return render_template(
        'clientes/detalle.html',
        cliente=cliente,
        ventas=ventas,
        creditos=creditos,
        abonos_cliente=abonos_cliente,
        from_creditos=from_creditos
    )

@clientes_bp.route('/<int:id>/historial/pdf')
@login_required
def historial_pdf(id):
    try:
        cliente = Cliente.query.get_or_404(id)
        ventas = Venta.query.filter_by(cliente_id=id).all()
        
        # Obtenemos abonos directamente desde las ventas
        abonos = []
        for venta in ventas:
            if hasattr(venta, 'abonos') and venta.abonos:
                abonos.extend(venta.abonos)
        
        # Pueden existir créditos directos, pero no es necesario para este PDF
        creditos = []
        
        pdf_bytes = generar_pdf_historial(cliente, ventas, creditos, abonos)
        response = make_response(pdf_bytes)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename=historial_cliente_{cliente.id}.pdf'
        return response
    except Exception as e:
        current_app.logger.error(f"Error generando historial PDF: {e}")
        flash(f"Error al generar el historial PDF: {str(e)}", "danger")
        return redirect(url_for('clientes.detalle', id=id))
