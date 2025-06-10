from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required
from app import db
from app.models import Configuracion
from app.forms import ConfiguracionForm
from app.decorators import admin_required
from werkzeug.utils import secure_filename
import os

config_bp = Blueprint('config', __name__, url_prefix='/config')

@config_bp.route('/', methods=['GET','POST'])
@login_required
@admin_required
def editar():
    config = Configuracion.query.first() or Configuracion()
    form = ConfiguracionForm(obj=config)
    
    if form.validate_on_submit():
        # Primero capturamos los valores del formulario pero sin sobrescribir el logo
        old_logo = config.logo
        
        # Actualizamos los campos simples
        config.nombre_empresa = form.nombre_empresa.data
        config.direccion = form.direccion.data
        config.telefono = form.telefono.data
        config.moneda = form.moneda.data
        
        # Asegurarnos de que el IVA sea un entero y pueda ser 0
        config.iva = int(form.iva.data) if form.iva.data is not None else 0
        
        # Comisiones separadas por rol
        config.porcentaje_comision_vendedor = form.porcentaje_comision_vendedor.data
        config.porcentaje_comision_cobrador = form.porcentaje_comision_cobrador.data
        config.periodo_comision = form.periodo_comision.data
        config.min_password = form.min_password.data
        
        # Procesar logo si se subió uno nuevo
        logo = form.logo.data
        if logo and logo.filename:
            # Validar tipo de archivo
            if logo.filename.split('.')[-1].lower() not in ['jpg', 'jpeg', 'png']:
                flash('Formato de imagen no permitido. Use JPG o PNG.', 'danger')
                return render_template('config/index.html', form=form, config=config)
                
            # Guardar logo
            logo_path = os.path.join(current_app.config['UPLOAD_FOLDER'], 'logo_' + secure_filename(logo.filename))
            logo.save(logo_path)
            config.logo = os.path.basename(logo_path)
        else:
            # Si no se subió un nuevo logo, mantener el anterior
            config.logo = old_logo
        
        # Guardar cambios
        try:
            db.session.commit()
            flash('Configuración actualizada exitosamente', 'success')
        except Exception as e:
            db.session.rollback()
            flash(f'Error al actualizar la configuración: {str(e)}', 'danger')
            
        return redirect(url_for('config.editar'))
        
    return render_template('config/index.html', form=form, config=config)
