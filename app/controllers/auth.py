from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from app import db, bcrypt
from app.models import Usuario
from app.forms import LoginForm

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    form = LoginForm()
    if form.validate_on_submit():
        user = Usuario.query.filter_by(email=form.email.data).first()
        if user and user.check_password(form.password.data):
            if not user.activo:
                flash('Su cuenta está desactivada. Contacte al administrador.', 'danger')
                return render_template('auth/login.html', form=form)

            login_user(user)
            next_page = request.args.get('next')
            flash(f'Bienvenido, {user.nombre}!', 'success')
            return redirect(next_page or url_for('dashboard.index'))
        else:
            flash('Inicio de sesión fallido. Verifique su email y contraseña.', 'danger')

    return render_template('auth/login.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Ha cerrado sesión exitosamente.', 'info')
    return redirect(url_for('auth.login'))