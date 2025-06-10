from flask import Blueprint, render_template
from flask_login import login_required, current_user
from app import db
from datetime import datetime
from app.models import Cliente, Producto, Venta, Abono, Caja
from app.utils import format_currency, get_comisiones_periodo

dashboard_bp = Blueprint('dashboard', __name__)

@dashboard_bp.route('/')
@login_required
def index():
    try:
        # Obtener la fecha actual
        now = datetime.now()
        primer_dia_mes = datetime(now.year, now.month, 1)

        # Filtro para vendedor
        vendedor_filter = {}
        if current_user.is_vendedor():
            vendedor_filter = {'vendedor_id': current_user.id}
        
        # Total de clientes (solo para vendedores y admin)
        if current_user.is_vendedor():
            # Obtener clientes de las ventas del vendedor
            clientes_ids = db.session.query(Venta.cliente_id).filter_by(vendedor_id=current_user.id).distinct()
            total_clientes = db.session.query(Cliente).filter(Cliente.id.in_(clientes_ids)).count()
        elif current_user.is_admin():
            total_clientes = Cliente.query.count()
        else:
            # Para cobradores, obtener clientes con créditos
            clientes_ids = db.session.query(Venta.cliente_id).filter(
                Venta.tipo == 'credito',
                Venta.saldo_pendiente > 0
            ).distinct()
            total_clientes = db.session.query(Cliente).filter(Cliente.id.in_(clientes_ids)).count()

        # Total de productos (solo para vendedores y admin)
        if current_user.is_vendedor() or current_user.is_admin():
            total_productos = Producto.query.count()
            productos_agotados = Producto.query.filter(Producto.stock <= 0).count()
            productos_stock_bajo = Producto.query.filter(Producto.stock <= Producto.stock_minimo, Producto.stock > 0).count()
        else:
            total_productos = 0
            productos_agotados = 0
            productos_stock_bajo = 0

        # Ventas del mes (solo para vendedores y admin)
        if current_user.is_vendedor() or current_user.is_admin():
            try:
                if current_user.is_vendedor():
                    todas_ventas = Venta.query.filter_by(vendedor_id=current_user.id).all()
                else:
                    todas_ventas = Venta.query.all()
                    
                ventas_mes = [v for v in todas_ventas if v.fecha and v.fecha >= primer_dia_mes]
                ventas_mes_count = len(ventas_mes)
                total_ventas_mes = sum(v.total for v in ventas_mes)
            except Exception as e:
                print(f"Error al consultar ventas: {e}")
                ventas_mes_count = 0
                total_ventas_mes = 0
        else:
            ventas_mes_count = 0
            total_ventas_mes = 0

        # Créditos activos (para todos los roles)
        try:
            if current_user.is_vendedor():
                todas_ventas = Venta.query.filter_by(vendedor_id=current_user.id).all()
            else:
                todas_ventas = Venta.query.all()
                
            creditos_activos = len([v for v in todas_ventas if v.tipo == 'credito' and v.saldo_pendiente and v.saldo_pendiente > 0])
            total_creditos = sum(v.saldo_pendiente for v in todas_ventas if v.tipo == 'credito' and v.saldo_pendiente and v.saldo_pendiente > 0)
        except Exception as e:
            print(f"Error al consultar créditos: {e}")
            creditos_activos = 0
            total_creditos = 0

        # Abonos del mes (para cobradores y admin)
        if current_user.is_cobrador() or current_user.is_admin():
            try:
                if current_user.is_cobrador():
                    abonos_mes = Abono.query.filter(
                        Abono.cobrador_id == current_user.id,
                        Abono.fecha >= primer_dia_mes
                    ).count()
                    
                    total_abonos_mes = db.session.query(db.func.sum(Abono.monto)).filter(
                        Abono.cobrador_id == current_user.id,
                        Abono.fecha >= primer_dia_mes
                    ).scalar() or 0
                else:
                    abonos_mes = Abono.query.filter(Abono.fecha >= primer_dia_mes).count()
                    total_abonos_mes = Abono.query.filter(Abono.fecha >= primer_dia_mes).with_entities(
                        db.func.sum(Abono.monto)).scalar() or 0
            except Exception as e:
                print(f"Error al consultar abonos: {e}")
                abonos_mes = 0
                total_abonos_mes = 0
        else:
            abonos_mes = 0
            total_abonos_mes = 0

        # Saldo en cajas (solo admin)
        if current_user.is_admin():
            try:
                cajas = Caja.query.all()
                total_cajas = sum(caja.saldo_actual for caja in cajas)
            except Exception as e:
                print(f"Error al consultar cajas: {e}")
                cajas = []
                total_cajas = 0
        else:
            total_cajas = 0

        # Comisión acumulada (para vendedores y cobradores)
        try:
            if current_user.is_vendedor() or current_user.is_cobrador():
                # Usar la función corregida con manejo de errores
                comisiones = get_comisiones_periodo(current_user.id)
            else:
                comisiones = get_comisiones_periodo()
                
            total_comision = sum(comision.monto_comision for comision in comisiones)
        except Exception as e:
            print(f"Error al consultar comisiones: {e}")
            comisiones = []
            total_comision = 0

        return render_template('dashboard/index.html',
                            total_clientes=total_clientes,
                            total_productos=total_productos,
                            productos_agotados=productos_agotados,
                            productos_stock_bajo=productos_stock_bajo,
                            ventas_mes=ventas_mes_count,
                            total_ventas_mes=format_currency(total_ventas_mes),
                            creditos_activos=creditos_activos,
                            total_creditos=format_currency(total_creditos),
                            abonos_mes=abonos_mes,
                            total_abonos_mes=format_currency(total_abonos_mes),
                            total_cajas=format_currency(total_cajas),
                            total_comision=format_currency(total_comision))
    except Exception as e:
        # Si ocurre cualquier error, mostrar una página alternativa
        print(f"Error general en dashboard: {e}")
        return render_template('error.html', 
                               mensaje="Lo sentimos, hubo un problema al cargar el dashboard. Estamos trabajando para solucionarlo.",
                               error=str(e))
