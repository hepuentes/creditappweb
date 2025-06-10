from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app import db, bcrypt
from app.models import Usuario
from app.forms import UsuarioForm
from app.decorators import admin_required

usuarios_bp = Blueprint('usuarios', __name__, url_prefix='/usuarios')

@usuarios_bp.route('/')
@login_required
@admin_required
def index():
    usuarios = Usuario.query.all()
    return render_template('usuarios/index.html', usuarios=usuarios)

@usuarios_bp.route('/crear', methods=['GET','POST'])
@login_required
@admin_required
def crear():
    form = UsuarioForm()
    if form.validate_on_submit():
        usuario = Usuario(
            nombre=form.nombre.data,
            email=form.email.data,
            rol=form.rol.data,
            activo=True
        )
        if form.password.data:
            usuario.set_password(form.password.data)
        db.session.add(usuario)
        db.session.commit()
        flash('Usuario creado exitosamente', 'success')
        return redirect(url_for('usuarios.index'))
    return render_template('usuarios/crear.html', form=form, titulo='Nuevo Usuario')

@usuarios_bp.route('/<int:id>/editar', methods=['GET','POST'])
@login_required
@admin_required
def editar(id):
    usuario = Usuario.query.get_or_404(id)
    form = UsuarioForm(obj=usuario)
    if form.validate_on_submit():
        usuario.nombre = form.nombre.data
        usuario.email = form.email.data
        usuario.rol = form.rol.data
        if form.activo.data is not None:
            usuario.activo = form.activo.data
        
        if form.password.data:
            usuario.set_password(form.password.data)
            
        db.session.commit()
        flash('Usuario actualizado exitosamente', 'success')
        return redirect(url_for('usuarios.index'))
    return render_template('usuarios/crear.html', form=form, titulo='Editar Usuario')

@usuarios_bp.route('/<int:id>/toggle_active', methods=['POST'])
@login_required
@admin_required
def toggle_active(id):
    usuario = Usuario.query.get_or_404(id)
    if usuario.id == 1:
        flash('No se puede modificar el estado del usuario administrador principal', 'danger')
    else:
        usuario.activo = not usuario.activo
        db.session.commit()
        estado = 'activado' if usuario.activo else 'desactivado'
        flash(f'Usuario {estado} exitosamente', 'success')
    return redirect(url_for('usuarios.index'))

@usuarios_bp.route('/<int:id>/eliminar', methods=['POST'])
@login_required
@admin_required
def eliminar(id):
    usuario = Usuario.query.get_or_404(id)
    if usuario.id == 1:
        flash('No se puede eliminar el usuario administrador principal', 'danger')
    elif usuario.id == current_user.id:
        flash('No se puede eliminar su propio usuario', 'danger')
    else:
        try:
            db.session.delete(usuario)
            db.session.commit()
            flash('Usuario eliminado exitosamente', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al eliminar el usuario: {str(e)}', 'danger')
    return redirect(url_for('usuarios.index'))

@usuarios_bp.route('/<int:id>')
@login_required
@admin_required
def detalle(id):
    usuario = Usuario.query.get_or_404(id)
    return render_template('usuarios/detalle.html', usuario=usuario)

@usuarios_bp.route('/mi-perfil')
@login_required
def mi_perfil():
    return render_template('usuarios/mi_perfil.html', usuario=current_user)

@usuarios_bp.route('/mi-perfil/editar', methods=['GET', 'POST'])
@login_required
def editar_mi_perfil():
    form = UsuarioForm(obj=current_user)
    
    # Remover el campo de rol para que no se pueda cambiar
    del form.rol
    del form.activo
    
    if form.validate_on_submit():
        # Verificar si el email ya existe en otro usuario
        if form.email.data != current_user.email:
            usuario_existente = Usuario.query.filter_by(email=form.email.data).first()
            if usuario_existente:
                flash('Ya existe otro usuario con ese email.', 'danger')
                return render_template('usuarios/editar_mi_perfil.html', form=form)
        
        # Actualizar datos
        current_user.nombre = form.nombre.data
        current_user.email = form.email.data
        
        # Cambiar contraseña solo si se proporcionó una nueva
        if form.password.data:
            current_user.set_password(form.password.data)
        
        db.session.commit()
        flash('Perfil actualizado exitosamente', 'success')
        return redirect(url_for('usuarios.mi_perfil'))
    
    return render_template('usuarios/editar_mi_perfil.html', form=form)
