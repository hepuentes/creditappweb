from flask import Blueprint, render_template, request, flash, redirect, url_for, make_response, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import *
from app.decorators import admin_required
import pandas as pd
from io import BytesIO
from datetime import datetime
import traceback

respaldos_bp = Blueprint('respaldos', __name__, url_prefix='/respaldos')

@respaldos_bp.route('/')
@login_required
@admin_required
def index():
    """Panel principal de respaldos con estadísticas del sistema"""
    try:
        # Obtener estadísticas del sistema
        estadisticas = {
            'usuarios': Usuario.query.count(),
            'clientes': Cliente.query.count(),
            'productos': Producto.query.count(),
            'ventas': Venta.query.count(),
            'abonos': Abono.query.count(),
            'comisiones': Comision.query.count(),
            'cajas': Caja.query.count(),
            'movimientos_caja': MovimientoCaja.query.count()
        }
        return render_template('respaldos/index.html', estadisticas=estadisticas)
    except Exception as e:
        current_app.logger.error(f"Error obteniendo estadísticas del sistema: {e}")
        estadisticas = {}
        return render_template('respaldos/index.html', estadisticas=estadisticas)

@respaldos_bp.route('/exportar-completo')
@login_required
@admin_required
def exportar_completo():
    """Exporta toda la información del sistema a Excel"""
    try:
        # Crear el archivo Excel en memoria
        output = BytesIO()
        
        with pd.ExcelWriter(output, engine='openpyxl') as writer:
            
            # 1. CONFIGURACIÓN
            try:
                config = Configuracion.query.first()
                if config:
                    config_data = [{
                        'id': config.id,
                        'nombre_empresa': config.nombre_empresa,
                        'direccion': config.direccion,
                        'telefono': config.telefono,
                        'moneda': config.moneda,
                        'iva': config.iva,
                        'porcentaje_comision_vendedor': config.porcentaje_comision_vendedor,
                        'porcentaje_comision_cobrador': config.porcentaje_comision_cobrador,
                        'periodo_comision': config.periodo_comision,
                        'min_password': config.min_password
                    }]
                    pd.DataFrame(config_data).to_excel(writer, sheet_name='Configuracion', index=False)
            except Exception as e:
                current_app.logger.error(f"Error exportando configuración: {e}")
            
            # 2. USUARIOS
            try:
                usuarios = Usuario.query.all()
                usuarios_data = []
                for usuario in usuarios:
                    usuarios_data.append({
                        'id': usuario.id,
                        'nombre': usuario.nombre,
                        'email': usuario.email,
                        'rol': usuario.rol,
                        'fecha_creacion': usuario.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S') if usuario.fecha_creacion else None
                    })
                pd.DataFrame(usuarios_data).to_excel(writer, sheet_name='Usuarios', index=False)
            except Exception as e:
                current_app.logger.error(f"Error exportando usuarios: {e}")
            
            # 3. CLIENTES
            try:
                clientes = Cliente.query.all()
                clientes_data = []
                for cliente in clientes:
                    clientes_data.append({
                        'id': cliente.id,
                        'nombre': cliente.nombre,
                        'telefono': cliente.telefono,
                        'direccion': cliente.direccion,
                        'email': cliente.email,
                        'fecha_creacion': cliente.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S') if cliente.fecha_creacion else None
                    })
                pd.DataFrame(clientes_data).to_excel(writer, sheet_name='Clientes', index=False)
            except Exception as e:
                current_app.logger.error(f"Error exportando clientes: {e}")
            
            # 4. PRODUCTOS
            try:
                productos = Producto.query.all()
                productos_data = []
                for producto in productos:
                    productos_data.append({
                        'id': producto.id,
                        'codigo': producto.codigo,
                        'nombre': producto.nombre,
                        'descripcion': producto.descripcion,
                        'precio_compra': producto.precio_compra,
                        'precio_venta': producto.precio_venta,
                        'stock': producto.stock,
                        'stock_minimo': getattr(producto, 'stock_minimo', 0),
                        'tiene_precio_individual': getattr(producto, 'tiene_precio_individual', False),
                        'precio_individual': getattr(producto, 'precio_individual', None),
                        'precio_kit': getattr(producto, 'precio_kit', None),
                        'cantidad_kit': getattr(producto, 'cantidad_kit', 1),
                        'fecha_registro': producto.fecha_registro.strftime('%Y-%m-%d %H:%M:%S') if producto.fecha_registro else None
                    })
                pd.DataFrame(productos_data).to_excel(writer, sheet_name='Productos', index=False)
            except Exception as e:
                current_app.logger.error(f"Error exportando productos: {e}")
            
            # 5. CAJAS
            try:
                cajas = Caja.query.all()
                cajas_data = []
                for caja in cajas:
                    cajas_data.append({
                        'id': caja.id,
                        'nombre': caja.nombre,
                        'tipo': caja.tipo,
                        'saldo_inicial': caja.saldo_inicial,
                        'saldo_actual': caja.saldo_actual,
                        'fecha_apertura': caja.fecha_apertura.strftime('%Y-%m-%d %H:%M:%S') if caja.fecha_apertura else None
                    })
                pd.DataFrame(cajas_data).to_excel(writer, sheet_name='Cajas', index=False)
            except Exception as e:
                current_app.logger.error(f"Error exportando cajas: {e}")
            
            # 6. VENTAS
            try:
                ventas = Venta.query.all()
                ventas_data = []
                for venta in ventas:
                    ventas_data.append({
                        'id': venta.id,
                        'fecha': venta.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                        'cliente_id': venta.cliente_id,
                        'cliente_nombre': venta.cliente.nombre if venta.cliente else 'N/A',
                        'vendedor_id': venta.vendedor_id,
                        'vendedor_nombre': venta.vendedor.nombre if venta.vendedor else 'N/A',
                        'tipo': venta.tipo,
                        'total': venta.total,
                        'saldo_pendiente': venta.saldo_pendiente,
                        'estado': venta.estado,
                        'numero_cuotas': getattr(venta, 'numero_cuotas', None),
                        'frecuencia_pago': getattr(venta, 'frecuencia_pago', None),
                        'valor_cuota': getattr(venta, 'valor_cuota', None),
                        'observaciones': getattr(venta, 'observaciones', None)
                    })
                pd.DataFrame(ventas_data).to_excel(writer, sheet_name='Ventas', index=False)
            except Exception as e:
                current_app.logger.error(f"Error exportando ventas: {e}")
            
            # 7. DETALLE VENTAS
            try:
                detalles = DetalleVenta.query.all()
                detalles_data = []
                for detalle in detalles:
                    detalles_data.append({
                        'id': detalle.id,
                        'venta_id': detalle.venta_id,
                        'producto_id': detalle.producto_id,
                        'producto_codigo': detalle.producto.codigo if detalle.producto else 'N/A',
                        'producto_nombre': detalle.producto.nombre if detalle.producto else 'N/A',
                        'cantidad': detalle.cantidad,
                        'precio_unitario': detalle.precio_unitario,
                        'subtotal': detalle.subtotal
                    })
                pd.DataFrame(detalles_data).to_excel(writer, sheet_name='VentasDetalle', index=False)
            except Exception as e:
                current_app.logger.error(f"Error exportando detalles de ventas: {e}")
            
            # 8. ABONOS
            try:
                abonos = Abono.query.all()
                abonos_data = []
                for abono in abonos:
                    abonos_data.append({
                        'id': abono.id,
                        'venta_id': abono.venta_id,
                        'cliente_nombre': abono.cliente.nombre if abono.cliente else 'N/A',
                        'cobrador_id': abono.cobrador_id,
                        'cobrador_nombre': abono.cobrador.nombre if abono.cobrador else 'N/A',
                        'monto': abono.monto,
                        'fecha': abono.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                        'caja_id': getattr(abono, 'caja_id', None),
                        'caja_nombre': abono.caja.nombre if hasattr(abono, 'caja') and abono.caja else 'N/A',
                        'notas': getattr(abono, 'notas', None)
                    })
                pd.DataFrame(abonos_data).to_excel(writer, sheet_name='Abonos', index=False)
            except Exception as e:
                current_app.logger.error(f"Error exportando abonos: {e}")
            
            # 9. COMISIONES
            try:
                comisiones = Comision.query.all()
                comisiones_data = []
                for comision in comisiones:
                    comisiones_data.append({
                        'id': comision.id,
                        'usuario_id': comision.usuario_id,
                        'usuario_nombre': comision.usuario.nombre if comision.usuario else 'N/A',
                        'monto_base': comision.monto_base,
                        'porcentaje': comision.porcentaje,
                        'monto_comision': comision.monto_comision,
                        'periodo': comision.periodo,
                        'pagado': comision.pagado,
                        'fecha_generacion': comision.fecha_generacion.strftime('%Y-%m-%d %H:%M:%S') if comision.fecha_generacion else None,
                        'venta_id': getattr(comision, 'venta_id', None),
                        'abono_id': getattr(comision, 'abono_id', None)
                    })
                pd.DataFrame(comisiones_data).to_excel(writer, sheet_name='Comisiones', index=False)
            except Exception as e:
                current_app.logger.error(f"Error exportando comisiones: {e}")
            
            # 10. MOVIMIENTOS DE CAJA
            try:
                movimientos = MovimientoCaja.query.all()
                movimientos_data = []
                for movimiento in movimientos:
                    movimientos_data.append({
                        'id': movimiento.id,
                        'caja_id': movimiento.caja_id,
                        'caja_nombre': movimiento.caja.nombre if movimiento.caja else 'N/A',
                        'tipo': movimiento.tipo,
                        'monto': movimiento.monto,
                        'descripcion': movimiento.descripcion,
                        'fecha': movimiento.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                        'venta_id': getattr(movimiento, 'venta_id', None),
                        'abono_id': getattr(movimiento, 'abono_id', None),
                        'caja_destino_id': getattr(movimiento, 'caja_destino_id', None)
                    })
                pd.DataFrame(movimientos_data).to_excel(writer, sheet_name='MovimientosCaja', index=False)
            except Exception as e:
                current_app.logger.error(f"Error exportando movimientos de caja: {e}")
            
            # 11. RESUMEN EJECUTIVO
            try:
                fecha_actual = datetime.now()
                resumen_data = [{
                    'fecha_respaldo': fecha_actual.strftime('%Y-%m-%d %H:%M:%S'),
                    'generado_por': current_user.email,
                    'total_usuarios': Usuario.query.count(),
                    'total_clientes': Cliente.query.count(),
                    'total_productos': Producto.query.count(),
                    'total_ventas': Venta.query.count(),
                    'total_abonos': Abono.query.count(),
                    'total_comisiones': Comision.query.count(),
                    'total_cajas': Caja.query.count(),
                    'total_movimientos_caja': MovimientoCaja.query.count(),
                    'ventas_pendientes': Venta.query.filter(Venta.saldo_pendiente > 0).count(),
                    'comisiones_pendientes': Comision.query.filter(Comision.pagado == False).count()
                }]
                pd.DataFrame(resumen_data).to_excel(writer, sheet_name='RESUMEN_RESPALDO', index=False)
            except Exception as e:
                current_app.logger.error(f"Error generando resumen: {e}")
        
        output.seek(0)
        
        # Crear respuesta de descarga
        fecha_actual = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'respaldo_creditapp_{fecha_actual}.xlsx'
        
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        current_app.logger.info(f"Respaldo completo generado por usuario {current_user.email}: {filename}")
        flash(f'Respaldo generado exitosamente: {filename}', 'success')
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error al generar respaldo completo: {e}")
        current_app.logger.error(traceback.format_exc())
        flash('Error al generar el respaldo. Contacte al administrador.', 'danger')
        return redirect(url_for('respaldos.index'))

@respaldos_bp.route('/api/estadisticas')
@login_required
@admin_required
def api_estadisticas():
    """API para obtener estadísticas actualizadas del sistema"""
    try:
        estadisticas = {
            'usuarios': Usuario.query.count(),
            'clientes': Cliente.query.count(),
            'productos': Producto.query.count(),
            'ventas': Venta.query.count(),
            'abonos': Abono.query.count(),
            'comisiones': Comision.query.count(),
            'cajas': Caja.query.count(),
            'movimientos_caja': MovimientoCaja.query.count(),
            'ultima_actualizacion': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }
        return estadisticas
    except Exception as e:
        current_app.logger.error(f"Error obteniendo estadísticas via API: {e}")
        return {'error': 'No se pudieron obtener las estadísticas'}, 500