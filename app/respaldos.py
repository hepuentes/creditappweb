from flask import Blueprint, render_template, request, flash, redirect, url_for, make_response, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.models import *
from app.decorators import admin_required
from werkzeug.utils import secure_filename
import pandas as pd
from io import BytesIO
from datetime import datetime
import os
import traceback
from sqlalchemy import text

respaldos_bp = Blueprint('respaldos', __name__, url_prefix='/respaldos')

@respaldos_bp.route('/')
@login_required
@admin_required
def index():
    return render_template('respaldos/index.html')

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
                        'nombre_empresa': config.nombre_empresa,
                        'direccion': config.direccion,
                        'telefono': config.telefono,
                        'iva': config.iva,
                        'moneda': config.moneda,
                        'porcentaje_comision_vendedor': config.porcentaje_comision_vendedor,
                        'porcentaje_comision_cobrador': config.porcentaje_comision_cobrador,
                        'periodo_comision': config.periodo_comision,
                        'min_password': config.min_password,
                        'logo': config.logo
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
                        'telefono': usuario.telefono,
                        'rol': usuario.rol,
                        'activo': usuario.activo,
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
                        'activo': cliente.activo,
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
                        'stock_minimo': producto.stock_minimo,
                        'activo': producto.activo,
                        'precios_diferenciados': producto.precios_diferenciados,
                        'precio_individual': producto.precio_individual,
                        'precio_kit': producto.precio_kit,
                        'cantidad_kit': producto.cantidad_kit
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
                        'descripcion': caja.descripcion,
                        'saldo_inicial': caja.saldo_inicial,
                        'saldo_actual': caja.saldo_actual,
                        'activa': caja.activa
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
                        'vendedor_id': venta.vendedor_id,
                        'tipo': venta.tipo,
                        'total': venta.total,
                        'saldo_pendiente': venta.saldo_pendiente,
                        'estado': venta.estado,
                        'numero_cuotas': venta.numero_cuotas,
                        'frecuencia_pago': venta.frecuencia_pago,
                        'valor_cuota': venta.valor_cuota,
                        'observaciones': venta.observaciones
                    })
                pd.DataFrame(ventas_data).to_excel(writer, sheet_name='Ventas', index=False)
            except Exception as e:
                current_app.logger.error(f"Error exportando ventas: {e}")
            
            # 7. VENTAS DETALLE
            try:
                ventas_detalle = VentaDetalle.query.all()
                detalle_data = []
                for detalle in ventas_detalle:
                    detalle_data.append({
                        'id': detalle.id,
                        'venta_id': detalle.venta_id,
                        'producto_id': detalle.producto_id,
                        'cantidad': detalle.cantidad,
                        'precio_unitario': detalle.precio_unitario,
                        'subtotal': detalle.subtotal
                    })
                pd.DataFrame(detalle_data).to_excel(writer, sheet_name='VentasDetalle', index=False)
            except Exception as e:
                current_app.logger.error(f"Error exportando ventas detalle: {e}")
            
            # 8. ABONOS
            try:
                abonos = Abono.query.all()
                abonos_data = []
                for abono in abonos:
                    abonos_data.append({
                        'id': abono.id,
                        'venta_id': abono.venta_id,
                        'cobrador_id': abono.cobrador_id,
                        'monto': abono.monto,
                        'fecha': abono.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                        'observaciones': abono.observaciones
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
                        'monto_base': comision.monto_base,
                        'porcentaje': comision.porcentaje,
                        'monto_comision': comision.monto_comision,
                        'periodo': comision.periodo,
                        'pagado': comision.pagado,
                        'fecha_generacion': comision.fecha_generacion.strftime('%Y-%m-%d %H:%M:%S') if comision.fecha_generacion else None,
                        'venta_id': comision.venta_id,
                        'abono_id': comision.abono_id
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
                        'tipo': movimiento.tipo,
                        'monto': movimiento.monto,
                        'descripcion': movimiento.descripcion,
                        'fecha': movimiento.fecha.strftime('%Y-%m-%d %H:%M:%S'),
                        'usuario_id': movimiento.usuario_id,
                        'venta_id': movimiento.venta_id,
                        'abono_id': movimiento.abono_id
                    })
                pd.DataFrame(movimientos_data).to_excel(writer, sheet_name='MovimientosCaja', index=False)
            except Exception as e:
                current_app.logger.error(f"Error exportando movimientos de caja: {e}")
        
        output.seek(0)
        
        # Crear respuesta de descarga
        fecha_actual = datetime.now().strftime('%Y%m%d_%H%M%S')
        filename = f'respaldo_creditapp_{fecha_actual}.xlsx'
        
        response = make_response(output.getvalue())
        response.headers['Content-Disposition'] = f'attachment; filename={filename}'
        response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
        
        current_app.logger.info(f"Respaldo completo generado: {filename}")
        return response
        
    except Exception as e:
        current_app.logger.error(f"Error al generar respaldo completo: {e}")
        current_app.logger.error(traceback.format_exc())
        flash('Error al generar el respaldo. Contacte al administrador.', 'danger')
        return redirect(url_for('respaldos.index'))

@respaldos_bp.route('/importar', methods=['GET', 'POST'])
@login_required
@admin_required
def importar():
    """Importar datos desde Excel"""
    if request.method == 'POST':
        if 'archivo' not in request.files:
            flash('No se ha seleccionado ningún archivo', 'danger')
            return redirect(request.url)
        
        archivo = request.files['archivo']
        if archivo.filename == '':
            flash('No se ha seleccionado ningún archivo', 'danger')
            return redirect(request.url)
        
        if archivo and archivo.filename.lower().endswith(('.xlsx', '.xls')):
            try:
                # Leer el archivo Excel
                excel_data = pd.read_excel(archivo, sheet_name=None)
                
                # Validar estructura del archivo
                validacion_resultado = validar_estructura_excel(excel_data)
                
                if not validacion_resultado['valido']:
                    flash(f'Estructura de archivo inválida: {validacion_resultado["errores"]}', 'danger')
                    return redirect(request.url)
                
                # Procesar la importación
                resultado = procesar_importacion(excel_data)
                
                if resultado['exito']:
                    flash(f'Importación exitosa: {resultado["mensaje"]}', 'success')
                else:
                    flash(f'Error en la importación: {resultado["error"]}', 'danger')
                
            except Exception as e:
                current_app.logger.error(f"Error al procesar archivo: {e}")
                current_app.logger.error(traceback.format_exc())
                flash('Error al procesar el archivo. Verifique el formato.', 'danger')
        else:
            flash('Formato de archivo no válido. Use .xlsx o .xls', 'danger')
    
    return render_template('respaldos/importar.html')

def validar_estructura_excel(excel_data):
    """Valida que el Excel tenga la estructura correcta"""
    hojas_requeridas = [
        'Configuracion', 'Usuarios', 'Clientes', 'Productos', 
        'Cajas', 'Ventas', 'VentasDetalle', 'Abonos', 
        'Comisiones', 'MovimientosCaja'
    ]
    
    errores = []
    
    # Verificar que existan las hojas
    for hoja in hojas_requeridas:
        if hoja not in excel_data:
            errores.append(f'Falta la hoja: {hoja}')
    
    # Validaciones específicas por hoja
    if 'Usuarios' in excel_data:
        df_usuarios = excel_data['Usuarios']
        columnas_requeridas = ['nombre', 'email', 'rol']
        for col in columnas_requeridas:
            if col not in df_usuarios.columns:
                errores.append(f'Falta columna "{col}" en hoja Usuarios')
    
    if 'Clientes' in excel_data:
        df_clientes = excel_data['Clientes']
        if 'nombre' not in df_clientes.columns:
            errores.append('Falta columna "nombre" en hoja Clientes')
    
    if 'Productos' in excel_data:
        df_productos = excel_data['Productos']
        columnas_requeridas = ['codigo', 'nombre', 'precio_venta']
        for col in columnas_requeridas:
            if col not in df_productos.columns:
                errores.append(f'Falta columna "{col}" en hoja Productos')
    
    return {
        'valido': len(errores) == 0,
        'errores': '; '.join(errores) if errores else None
    }

def procesar_importacion(excel_data):
    """Procesa la importación de datos con transacciones atómicas"""
    try:
        registros_procesados = 0
        
        # Iniciar transacción
        with db.session.begin():
            
            # 1. CONFIGURACIÓN (solo actualizar, no insertar)
            if 'Configuracion' in excel_data and not excel_data['Configuracion'].empty:
                df_config = excel_data['Configuracion']
                config = Configuracion.query.first()
                if config and len(df_config) > 0:
                    row = df_config.iloc[0]
                    config.nombre_empresa = row.get('nombre_empresa', config.nombre_empresa)
                    config.direccion = row.get('direccion', config.direccion)
                    config.telefono = row.get('telefono', config.telefono)
                    if pd.notna(row.get('iva')):
                        config.iva = int(row['iva'])
                    config.moneda = row.get('moneda', config.moneda)
                    if pd.notna(row.get('porcentaje_comision_vendedor')):
                        config.porcentaje_comision_vendedor = int(row['porcentaje_comision_vendedor'])
                    if pd.notna(row.get('porcentaje_comision_cobrador')):
                        config.porcentaje_comision_cobrador = int(row['porcentaje_comision_cobrador'])
                    config.periodo_comision = row.get('periodo_comision', config.periodo_comision)
                    if pd.notna(row.get('min_password')):
                        config.min_password = int(row['min_password'])
                    registros_procesados += 1
            
            # 2. USUARIOS (omitir duplicados por email)
            if 'Usuarios' in excel_data and not excel_data['Usuarios'].empty:
                df_usuarios = excel_data['Usuarios']
                for _, row in df_usuarios.iterrows():
                    if pd.isna(row['email']) or pd.isna(row['nombre']):
                        continue
                    
                    # Verificar si ya existe
                    usuario_existente = Usuario.query.filter_by(email=row['email']).first()
                    if usuario_existente:
                        continue  # Omitir duplicados
                    
                    nuevo_usuario = Usuario(
                        nombre=row['nombre'],
                        email=row['email'],
                        telefono=row.get('telefono'),
                        rol=row.get('rol', 'vendedor'),
                        activo=row.get('activo', True)
                    )
                    # Nota: La contraseña se debe establecer por separado
                    nuevo_usuario.set_password('123456')  # Contraseña temporal
                    db.session.add(nuevo_usuario)
                    registros_procesados += 1
            
            # 3. CLIENTES (omitir duplicados por teléfono)
            if 'Clientes' in excel_data and not excel_data['Clientes'].empty:
                df_clientes = excel_data['Clientes']
                for _, row in df_clientes.iterrows():
                    if pd.isna(row['nombre']):
                        continue
                    
                    # Verificar duplicados por teléfono si existe
                    cliente_existente = None
                    if pd.notna(row.get('telefono')):
                        cliente_existente = Cliente.query.filter_by(telefono=row['telefono']).first()
                    
                    if cliente_existente:
                        continue  # Omitir duplicados
                    
                    nuevo_cliente = Cliente(
                        nombre=row['nombre'],
                        telefono=row.get('telefono'),
                        direccion=row.get('direccion'),
                        email=row.get('email'),
                        activo=row.get('activo', True)
                    )
                    db.session.add(nuevo_cliente)
                    registros_procesados += 1
            
            # 4. PRODUCTOS (omitir duplicados por código)
            if 'Productos' in excel_data and not excel_data['Productos'].empty:
                df_productos = excel_data['Productos']
                for _, row in df_productos.iterrows():
                    if pd.isna(row['codigo']) or pd.isna(row['nombre']):
                        continue
                    
                    # Verificar duplicados por código
                    producto_existente = Producto.query.filter_by(codigo=row['codigo']).first()
                    if producto_existente:
                        continue  # Omitir duplicados
                    
                    nuevo_producto = Producto(
                        codigo=row['codigo'],
                        nombre=row['nombre'],
                        descripcion=row.get('descripcion'),
                        precio_compra=int(row.get('precio_compra', 0)) if pd.notna(row.get('precio_compra')) else None,
                        precio_venta=int(row['precio_venta']),
                        stock=int(row.get('stock', 0)),
                        stock_minimo=int(row.get('stock_minimo', 0)),
                        activo=row.get('activo', True),
                        precios_diferenciados=row.get('precios_diferenciados', False),
                        precio_individual=int(row.get('precio_individual', 0)) if pd.notna(row.get('precio_individual')) else None,
                        precio_kit=int(row.get('precio_kit', 0)) if pd.notna(row.get('precio_kit')) else None,
                        cantidad_kit=int(row.get('cantidad_kit', 1)) if pd.notna(row.get('cantidad_kit')) else 1
                    )
                    db.session.add(nuevo_producto)
                    registros_procesados += 1
            
            # 5. CAJAS (omitir duplicados por nombre)
            if 'Cajas' in excel_data and not excel_data['Cajas'].empty:
                df_cajas = excel_data['Cajas']
                for _, row in df_cajas.iterrows():
                    if pd.isna(row['nombre']):
                        continue
                    
                    # Verificar duplicados por nombre
                    caja_existente = Caja.query.filter_by(nombre=row['nombre']).first()
                    if caja_existente:
                        continue  # Omitir duplicados
                    
                    nueva_caja = Caja(
                        nombre=row['nombre'],
                        descripcion=row.get('descripcion'),
                        saldo_inicial=int(row.get('saldo_inicial', 0)),
                        saldo_actual=int(row.get('saldo_actual', row.get('saldo_inicial', 0))),
                        activa=row.get('activa', True)
                    )
                    db.session.add(nueva_caja)
                    registros_procesados += 1
            
            # Hacer flush para obtener los IDs de los registros insertados
            db.session.flush()
            
            # 6-10. VENTAS, DETALLES, ABONOS, etc. se procesarían aquí
            # Por ahora implementamos solo la estructura base
            
        return {
            'exito': True,
            'mensaje': f'{registros_procesados} registros procesados exitosamente'
        }
        
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error en importación: {e}")
        current_app.logger.error(traceback.format_exc())
        return {
            'exito': False,
            'error': str(e)
        }