from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app import db
from app.models import Producto
from app.forms import ProductoForm
from app.decorators import vendedor_required, admin_required

productos_bp = Blueprint('productos', __name__, url_prefix='/productos')

@productos_bp.route('/')
@login_required
@vendedor_required
def index():
    busqueda = request.args.get('busqueda', '')
    query = Producto.query
    if busqueda:
        query = query.filter(Producto.nombre.ilike(f"%{busqueda}%"))
    productos = query.all()
    # Pasamos el flag de solo_consulta para vendedores
    solo_consulta = current_user.is_vendedor() and not current_user.is_admin()
    return render_template('productos/index.html', productos=productos, busqueda=busqueda, solo_consulta=solo_consulta)

@productos_bp.route('/<int:id>')
@login_required
@vendedor_required
def detalle(id):
    producto = Producto.query.get_or_404(id)
    form = ProductoForm(obj=producto)
    return render_template('productos/detalle.html', producto=producto, form=form)

@productos_bp.route('/crear', methods=['GET', 'POST'])
@login_required
@admin_required
def crear():
    form = ProductoForm()
    if form.validate_on_submit():
        # Validación: Verificar si el código ya existe
        codigo_existente = Producto.query.filter_by(codigo=form.codigo.data).first()
        if codigo_existente:
            flash('⚠️ El código del producto ya existe. Usa otro código.', 'warning')
            return render_template('productos/crear.html', form=form)

        nuevo = Producto()
        form.populate_obj(nuevo)
        db.session.add(nuevo)
        db.session.commit()
        flash('✅ Producto creado', 'success')
        return redirect(url_for('productos.index'))
    return render_template('productos/crear.html', form=form)

@productos_bp.route('/<int:id>/editar', methods=['GET','POST'])
@login_required
@admin_required
def editar(id):
    producto = Producto.query.get_or_404(id)
    form = ProductoForm(obj=producto)
    if form.validate_on_submit():
        form.populate_obj(producto)
        db.session.commit()
        flash('Producto actualizado', 'success')
        return redirect(url_for('productos.index'))
    return render_template('productos/crear.html', form=form)

@productos_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def eliminar(id):
    producto = Producto.query.get_or_404(id)
    try:
        db.session.delete(producto)
        db.session.commit()
        flash('Producto eliminado exitosamente', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Error al eliminar el producto: {str(e)}', 'danger')
    return redirect(url_for('productos.index'))
