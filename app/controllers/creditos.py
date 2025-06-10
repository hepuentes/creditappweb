from flask import Blueprint, render_template, redirect, url_for, flash, request, make_response, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Credito, Cliente, Venta
from app.forms import CreditoForm
from app.decorators import cobrador_required, vendedor_cobrador_required
from app.pdf.credito import generar_pdf_credito
from datetime import datetime

creditos_bp = Blueprint('creditos', __name__, url_prefix='/creditos')

@creditos_bp.route('/')
@login_required
@vendedor_cobrador_required
def index():
    try:
        # Obtener parámetros de filtro
        busqueda = request.args.get('busqueda', '')
        desde_str = request.args.get('desde', '')
        hasta_str = request.args.get('hasta', '')
        
        # Consulta base: ventas a crédito con saldo pendiente
        query = Venta.query.filter(
            Venta.tipo == 'credito',
            Venta.saldo_pendiente > 0
        )
        
        # Si es vendedor, filtrar por sus propias ventas
        if current_user.is_vendedor():
            query = query.filter(Venta.vendedor_id == current_user.id)
        
        if busqueda:
            # Buscar por nombre de cliente
            query = query.join(Cliente).filter(Cliente.nombre.ilike(f"%{busqueda}%"))
        
        if desde_str:
            try:
                desde_dt = datetime.strptime(desde_str, '%Y-%m-%d')
                query = query.filter(Venta.fecha >= desde_dt)
            except ValueError:
                flash('Fecha "desde" inválida.', 'warning')
        
        if hasta_str:
            try:
                hasta_dt = datetime.strptime(hasta_str, '%Y-%m-%d')
                hasta_dt_fin_dia = datetime.combine(hasta_dt, datetime.max.time())
                query = query.filter(Venta.fecha <= hasta_dt_fin_dia)
            except ValueError:
                flash('Fecha "hasta" inválida.', 'warning')

        # Ordenar por fecha descendente
        creditos = query.order_by(Venta.fecha.desc()).all()
        
        # Calcular totales
        total_creditos = sum(c.total for c in creditos)
        total_pendiente = sum(c.saldo_pendiente for c in creditos)
        
        return render_template('creditos/index.html', 
                              creditos=creditos, 
                              total_creditos=total_creditos,
                              total_pendiente=total_pendiente,
                              busqueda=busqueda,
                              desde=desde_str,
                              hasta=hasta_str)
    except Exception as e:
        # En caso de error, mostrar mensaje y devolver plantilla con datos vacíos
        flash(f'Error al cargar créditos: {str(e)}', 'danger')
        return render_template('creditos/index.html', 
                              creditos=[],
                              total_creditos=0,
                              total_pendiente=0)
