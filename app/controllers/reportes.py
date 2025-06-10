from flask import Blueprint, render_template, redirect, url_for, request, make_response, flash, jsonify, current_app
from flask_login import login_required, current_user
from app import db
from app.models import Comision, Usuario, Venta, Abono, MovimientoCaja
from app.forms import ReporteComisionesForm
from app.decorators import admin_required, vendedor_extended_required, vendedor_cobrador_required
from datetime import datetime, timedelta
import csv
import io
import pandas as pd
from io import BytesIO


reportes_bp = Blueprint('reportes', __name__, url_prefix='/reportes')

@reportes_bp.route('/comisiones', methods=['GET', 'POST'])
@login_required
@vendedor_cobrador_required  
def comisiones():
    form = ReporteComisionesForm()
    comisiones_por_usuario = {}
    total_base = 0
    total_comision = 0
    fecha_inicio = None
    fecha_fin = None
    pagination = None

    # Si el usuario es vendedor o cobrador, solo mostrar sus propias comisiones
    if (current_user.is_vendedor() or current_user.is_cobrador()) and not current_user.is_admin():
        form.usuario_id.choices = [(current_user.id, current_user.nombre)]
        form.usuario_id.data = current_user.id
    else:
        # Cargar usuarios para el select (admin ve todos)
        usuarios = Usuario.query.filter(Usuario.rol.in_(['vendedor', 'cobrador', 'administrador'])).all()
        form.usuario_id.choices = [(0, 'Todos')] + [(u.id, u.nombre) for u in usuarios]

    # Valores por defecto para fechas
    today = datetime.now()
    primer_dia_mes = datetime(today.year, today.month, 1)
    if today.month == 12:
        ultimo_dia_mes = datetime(today.year + 1, 1, 1) - timedelta(days=1)
    else:
        ultimo_dia_mes = datetime(today.year, today.month + 1, 1) - timedelta(days=1)

    # Establecer valores por defecto para las fechas si es GET
    if request.method == 'GET':
        form.fecha_inicio.data = primer_dia_mes.strftime('%Y-%m-%d')
        form.fecha_fin.data = ultimo_dia_mes.strftime('%Y-%m-%d')

    # Si se envía el formulario
    if form.validate_on_submit():
        try:
            fecha_inicio = datetime.strptime(form.fecha_inicio.data, '%Y-%m-%d')
            fecha_fin = datetime.strptime(form.fecha_fin.data, '%Y-%m-%d')
            usuario_id = form.usuario_id.data
            
            # Para vendedores y cobradores, siempre usar su ID
            if (current_user.is_vendedor() or current_user.is_cobrador()) and not current_user.is_admin():
                usuario_id = current_user.id
            
            # Usar la función corregida con manejo de errores
            try:
                # Crear consulta manualmente para mejor control de errores
                base_query = db.session.query(Comision, Usuario)\
                    .join(Usuario, Comision.usuario_id == Usuario.id)\
                    .filter(
                        Comision.fecha_generacion >= fecha_inicio,
                        Comision.fecha_generacion <= fecha_fin
                    )
                
                if usuario_id and usuario_id != 0:
                    base_query = base_query.filter(Comision.usuario_id == usuario_id)
                
                # Ejecutar consulta con manejo de errores
                try:
                    all_comisiones = base_query.all()
                except Exception as db_error:
                    # Rollback y reintentar
                    db.session.rollback()
                    current_app.logger.error(f"Error en consulta comisiones: {db_error}")
                    all_comisiones = base_query.all()
                
                # Procesar resultados
                comisiones_paginadas = all_comisiones[:25]  # Limitar para evitar problemas
                
                if not comisiones_paginadas and (current_user.is_vendedor() or current_user.is_cobrador()):
                    flash('No se encontraron comisiones registradas para este período.', 'info')
                
                # Agrupar por usuario
                for comision, usuario in comisiones_paginadas:
                    if usuario.id not in comisiones_por_usuario:
                        comisiones_por_usuario[usuario.id] = {
                            'usuario': usuario,
                            'comisiones': [],
                            'total_base': 0,
                            'total_comision': 0
                        }

                    comisiones_por_usuario[usuario.id]['comisiones'].append(comision)
                    comisiones_por_usuario[usuario.id]['total_base'] += comision.monto_base
                    comisiones_por_usuario[usuario.id]['total_comision'] += comision.monto_comision
                
                # Calcular totales generales
                for comision, usuario in all_comisiones:
                    total_base += comision.monto_base
                    total_comision += comision.monto_comision

                # Si se solicita exportar Excel
                if 'export' in request.form:
                    return exportar_excel_comisiones([c for c, _ in all_comisiones], fecha_inicio, fecha_fin)
                    
            except Exception as query_error:
                current_app.logger.error(f"Error en procesamiento de comisiones: {query_error}")
                flash("Error al procesar las comisiones. Intente nuevamente.", "danger")
                db.session.rollback()
                
        except Exception as e:
            current_app.logger.error(f"Error al generar reporte de comisiones: {str(e)}")
            flash(f"Error al generar el reporte: {str(e)}", "danger")
            db.session.rollback()

    return render_template('reportes/comisiones.html',
                          form=form,
                          comisiones_por_usuario=comisiones_por_usuario,
                          total_base=total_base,
                          total_comision=total_comision,
                          fecha_inicio=fecha_inicio,
                          fecha_fin=fecha_fin,
                          pagination=pagination)


@reportes_bp.route('/comisiones/liquidar-masiva', methods=['GET', 'POST'])
@login_required
@admin_required
def liquidar_masiva():
    if request.method == 'POST':
        # Obtener fechas del formulario
        fecha_inicio = datetime.strptime(request.form['fecha_inicio'], '%Y-%m-%d')
        fecha_fin = datetime.strptime(request.form['fecha_fin'], '%Y-%m-%d')
        usuario_id = request.form.get('usuario_id')
        
        try:
            # Construir consulta con mejor manejo de errores
            query = Comision.query.filter(
                Comision.fecha_generacion >= fecha_inicio,
                Comision.fecha_generacion <= fecha_fin,
                Comision.pagado == False
            )
            
            if usuario_id and usuario_id != '0':
                query = query.filter(Comision.usuario_id == usuario_id)
            
            # Ejecutar consulta con manejo de errores
            try:
                comisiones = query.all()
            except Exception as db_error:
                db.session.rollback()
                current_app.logger.error(f"Error en consulta liquidación masiva: {db_error}")
                comisiones = query.all()
            
            if 'liquidar' in request.form:
                # Marcar todas como pagadas
                for comision in comisiones:
                    comision.pagado = True
                
                db.session.commit()
                total_liquidado = sum(c.monto_comision for c in comisiones)
                flash(f'Liquidadas {len(comisiones)} comisiones por un total de ${total_liquidado:,.0f}', 'success')
                return redirect(url_for('reportes.liquidar_masiva'))
            
            elif 'exportar' in request.form:
                # Exportar a Excel
                return exportar_excel_liquidacion(comisiones, fecha_inicio, fecha_fin)
            
            # Agrupar por usuario para mostrar resumen
            resumen_usuarios = {}
            for comision in comisiones:
                if comision.usuario_id not in resumen_usuarios:
                    resumen_usuarios[comision.usuario_id] = {
                        'usuario': comision.usuario,
                        'total_comision': 0,
                        'cantidad': 0
                    }
                resumen_usuarios[comision.usuario_id]['total_comision'] += comision.monto_comision
                resumen_usuarios[comision.usuario_id]['cantidad'] += 1
            
            return render_template('reportes/liquidar_masiva.html', 
                                 resumen_usuarios=resumen_usuarios,
                                 fecha_inicio=fecha_inicio,
                                 fecha_fin=fecha_fin,
                                 total_general=sum(c.monto_comision for c in comisiones))
        
        except Exception as e:
            current_app.logger.error(f"Error en liquidación masiva: {e}")
            flash(f"Error en liquidación masiva: {str(e)}", "danger")
            db.session.rollback()
    
    # GET: mostrar formulario
    usuarios = Usuario.query.filter(Usuario.rol.in_(['vendedor', 'cobrador', 'administrador'])).all()
    return render_template('reportes/liquidar_masiva.html', usuarios=usuarios)

@reportes_bp.route('/comisiones/<int:id>/marcar-pagado', methods=['POST'])
@login_required
@admin_required
def marcar_pagado(id):
    comision = Comision.query.get_or_404(id)
    comision.pagado = True
    db.session.commit()
    flash('Comisión marcada como pagada exitosamente', 'success')
    # No redirigir para evitar resetear filtros
    return jsonify({'success': True})

@reportes_bp.route('/comisiones/marcar-todas-pagadas', methods=['POST'])
@login_required
@admin_required
def marcar_todas_pagadas():
    data = request.get_json()
    comision_ids = data.get('comision_ids', [])
    
    if comision_ids:
        comisiones = Comision.query.filter(Comision.id.in_(comision_ids)).all()
        for comision in comisiones:
            comision.pagado = True
        db.session.commit()
        flash(f'{len(comisiones)} comisiones marcadas como pagadas exitosamente', 'success')
        return jsonify({'success': True, 'count': len(comisiones)})
    
    return jsonify({'success': False, 'error': 'No se seleccionaron comisiones'})


def exportar_excel_liquidacion(comisiones, fecha_inicio, fecha_fin):
    """Exporta liquidación de comisiones a Excel"""
    data = []
    
    # Agrupar por usuario
    usuarios_dict = {}
    for comision in comisiones:
        if comision.usuario_id not in usuarios_dict:
            usuarios_dict[comision.usuario_id] = {
                'nombre': comision.usuario.nombre,
                'comisiones': [],
                'total': 0
            }
        usuarios_dict[comision.usuario_id]['comisiones'].append(comision)
        usuarios_dict[comision.usuario_id]['total'] += comision.monto_comision
    
    # Crear data para Excel
    for usuario_id, datos in usuarios_dict.items():
        # Fila de resumen del usuario
        data.append({
            'EMPLEADO': datos['nombre'],
            'CONCEPTO': 'TOTAL A PAGAR',
            'CANTIDAD': len(datos['comisiones']),
            'MONTO': f"${datos['total']:,.0f}",
            'PERIODO': f"{fecha_inicio.strftime('%d/%m/%Y')} - {fecha_fin.strftime('%d/%m/%Y')}"
        })
        
        # Detalle de cada comisión
        for comision in datos['comisiones']:
            origen = "Venta" if comision.venta_id else "Abono" if comision.abono_id else "N/A"
            data.append({
                'EMPLEADO': '',
                'CONCEPTO': f"{origen} #{comision.venta_id or comision.abono_id or 'N/A'}",
                'CANTIDAD': f"{comision.porcentaje}%",
                'MONTO': f"${comision.monto_comision:,.0f}",
                'PERIODO': comision.fecha_generacion.strftime('%d/%m/%Y')
            })
        
        # Fila vacía entre empleados
        data.append({'EMPLEADO': '', 'CONCEPTO': '', 'CANTIDAD': '', 'MONTO': '', 'PERIODO': ''})
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Liquidación Comisiones', index=False)
        
        # Formatear el Excel
        workbook = writer.book
        worksheet = writer.sheets['Liquidación Comisiones']
        
        # Ajustar anchos de columna
        worksheet.column_dimensions['A'].width = 20
        worksheet.column_dimensions['B'].width = 25
        worksheet.column_dimensions['C'].width = 15
        worksheet.column_dimensions['D'].width = 15
        worksheet.column_dimensions['E'].width = 20
    
    output.seek(0)
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=liquidacion_comisiones_{fecha_inicio.strftime("%Y%m%d")}-{fecha_fin.strftime("%Y%m%d")}.xlsx'
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    return response

# NUEVOS REPORTES
@reportes_bp.route('/ventas', methods=['GET', 'POST'])
@login_required
@vendedor_cobrador_required
def ventas():
    if request.method == 'POST':
        fecha_inicio = datetime.strptime(request.form['fecha_inicio'], '%Y-%m-%d')
        fecha_fin = datetime.strptime(request.form['fecha_fin'], '%Y-%m-%d')
        
        query = Venta.query.filter(
            Venta.fecha >= fecha_inicio,
            Venta.fecha <= fecha_fin
        )
        
        # Si es vendedor, filtrar solo sus ventas
        if current_user.is_vendedor() and not current_user.is_admin():
            query = query.filter(Venta.vendedor_id == current_user.id)
        
        ventas = query.all()
        
        if 'export' in request.form:
            return exportar_excel_ventas(ventas, fecha_inicio, fecha_fin)
        
        return render_template('reportes/ventas.html', ventas=ventas, 
                             fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
    
    return render_template('reportes/ventas.html')

@reportes_bp.route('/abonos', methods=['GET', 'POST'])
@login_required
@vendedor_cobrador_required
def abonos():
    if request.method == 'POST':
        fecha_inicio = datetime.strptime(request.form['fecha_inicio'], '%Y-%m-%d')
        fecha_fin = datetime.strptime(request.form['fecha_fin'], '%Y-%m-%d')
        
        query = Abono.query.filter(
            Abono.fecha >= fecha_inicio,
            Abono.fecha <= fecha_fin  
        )
        
        # Si es vendedor, filtrar solo abonos de sus ventas
        if current_user.is_vendedor() and not current_user.is_admin():
            query = query.join(Venta).filter(Venta.vendedor_id == current_user.id)
        
        abonos = query.all()
        
        if 'export' in request.form:
            return exportar_excel_abonos(abonos, fecha_inicio, fecha_fin)
        
        return render_template('reportes/abonos.html', abonos=abonos,
                             fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
    
    return render_template('reportes/abonos.html')

@reportes_bp.route('/egresos', methods=['GET', 'POST'])
@login_required
@admin_required
def egresos():
    if request.method == 'POST':
        fecha_inicio = datetime.strptime(request.form['fecha_inicio'], '%Y-%m-%d')
        fecha_fin = datetime.strptime(request.form['fecha_fin'], '%Y-%m-%d')
        
        # Ajustar fecha_fin para incluir todo el día
        fecha_fin_completa = datetime.combine(fecha_fin, datetime.max.time())
        
        egresos = MovimientoCaja.query.filter(
            MovimientoCaja.tipo == 'salida',
            MovimientoCaja.fecha >= fecha_inicio,
            MovimientoCaja.fecha <= fecha_fin_completa
        ).all()
        
        # DEBUG: Agregar información de debug
        current_app.logger.info(f"Buscando egresos desde {fecha_inicio} hasta {fecha_fin_completa}")
        current_app.logger.info(f"Encontrados {len(egresos)} egresos")
        
        # Si no encuentra egresos, mostrar todos los movimientos para debug
        if not egresos:
            todos_movimientos = MovimientoCaja.query.filter(
                MovimientoCaja.fecha >= fecha_inicio,
                MovimientoCaja.fecha <= fecha_fin_completa
            ).all()
            current_app.logger.info(f"Total movimientos en el período: {len(todos_movimientos)}")
            for mov in todos_movimientos:
                current_app.logger.info(f"Movimiento ID: {mov.id}, Tipo: {mov.tipo}, Fecha: {mov.fecha}, Monto: {mov.monto}")
        
        if 'export' in request.form:
            return exportar_excel_egresos(egresos, fecha_inicio, fecha_fin)
        
        return render_template('reportes/egresos.html', egresos=egresos,
                             fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
    
    return render_template('reportes/egresos.html')

def exportar_excel_comisiones(comisiones, fecha_inicio, fecha_fin):
    """Exporta las comisiones a un archivo Excel con formato correcto"""
    data = []
    for comision in comisiones:
        origen = "N/A"
        if hasattr(comision, 'venta_id') and comision.venta_id and comision.venta:
            origen = f"Venta #{comision.venta_id} - {comision.venta.cliente.nombre}"
        elif hasattr(comision, 'abono_id') and comision.abono_id and comision.abono:
            origen = f"Abono #{comision.abono_id} - Venta #{comision.abono.venta_id}"
            
        data.append({
            'ID': comision.id,
            'Fecha': comision.fecha_generacion.strftime('%d/%m/%Y %H:%M'),
            'Usuario': comision.usuario.nombre,
            'Monto Base': int(comision.monto_base),
            'Porcentaje': f"{comision.porcentaje}%",
            'Monto Comision': int(comision.monto_comision),
            'Periodo': comision.periodo,
            'Origen': origen,
            'Pagado': 'Si' if comision.pagado else 'No'
        })
    
    df = pd.DataFrame(data)
    
    # Crear el archivo Excel en memoria
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Comisiones', index=False)
    
    output.seek(0)
    
    # Crear respuesta
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=comisiones_{fecha_inicio.strftime("%Y%m%d")}-{fecha_fin.strftime("%Y%m%d")}.xlsx'
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    return response

def exportar_excel_ventas(ventas, fecha_inicio, fecha_fin):
    """Exporta las ventas a Excel"""
    data = []
    for venta in ventas:
        data.append({
            'ID': venta.id,
            'Fecha': venta.fecha.strftime('%d/%m/%Y %H:%M'),
            'Cliente': venta.cliente.nombre,
            'Vendedor': venta.vendedor.nombre,
            'Tipo': venta.tipo.title(),
            'Total': int(venta.total),
            'Saldo Pendiente': int(venta.saldo_pendiente) if venta.saldo_pendiente else 0,
            'Estado': venta.estado.title()
        })
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Ventas', index=False)
    
    output.seek(0)
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=ventas_{fecha_inicio.strftime("%Y%m%d")}-{fecha_fin.strftime("%Y%m%d")}.xlsx'
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    return response

def exportar_excel_abonos(abonos, fecha_inicio, fecha_fin):
    """Exporta los abonos a Excel"""
    data = []
    for abono in abonos:
        data.append({
            'ID': abono.id,
            'Fecha': abono.fecha.strftime('%d/%m/%Y %H:%M'),
            'Cliente': abono.venta.cliente.nombre if abono.venta else 'N/A',
            'Factura': f"#{abono.venta_id}" if abono.venta_id else 'N/A',
            'Monto': int(abono.monto),
            'Cobrador': abono.cobrador.nombre,
            'Caja': abono.caja.nombre if abono.caja else 'N/A',
            'Notas': abono.notas or 'Sin notas'
        })
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Abonos', index=False)
    
    output.seek(0)
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=abonos_{fecha_inicio.strftime("%Y%m%d")}-{fecha_fin.strftime("%Y%m%d")}.xlsx'
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    return response

def exportar_excel_egresos(egresos, fecha_inicio, fecha_fin):
    """Exporta los egresos a Excel"""
    data = []
    for egreso in egresos:
        data.append({
            'ID': egreso.id,
            'Fecha': egreso.fecha.strftime('%d/%m/%Y %H:%M'),
            'Caja': egreso.caja.nombre,
            'Monto': int(egreso.monto),
            'Descripcion': egreso.descripcion or 'Sin descripcion'
        })
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Egresos', index=False)
    
    output.seek(0)
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=egresos_{fecha_inicio.strftime("%Y%m%d")}-{fecha_fin.strftime("%Y%m%d")}.xlsx'
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    return response

@reportes_bp.route('/creditos', methods=['GET', 'POST'])
@login_required
@vendedor_cobrador_required
def creditos():
    if request.method == 'POST':
        fecha_inicio = datetime.strptime(request.form['fecha_inicio'], '%Y-%m-%d')
        fecha_fin = datetime.strptime(request.form['fecha_fin'], '%Y-%m-%d')
        
        query = Venta.query.filter(
            Venta.tipo == 'credito',
            Venta.fecha >= fecha_inicio,
            Venta.fecha <= fecha_fin
        )
        
        # Si es vendedor, filtrar solo sus ventas
        if current_user.is_vendedor() and not current_user.is_admin():
            query = query.filter(Venta.vendedor_id == current_user.id)
        
        creditos = query.all()
        
        if 'export' in request.form:
            return exportar_excel_creditos(creditos, fecha_inicio, fecha_fin)
        
        return render_template('reportes/creditos.html', creditos=creditos,
                             fecha_inicio=fecha_inicio, fecha_fin=fecha_fin)
    
    return render_template('reportes/creditos.html')

def exportar_excel_creditos(creditos, fecha_inicio, fecha_fin):
    """Exporta los créditos a Excel"""
    data = []
    for credito in creditos:
        data.append({
            'ID': credito.id,
            'Fecha': credito.fecha.strftime('%d/%m/%Y %H:%M'),
            'Cliente': credito.cliente.nombre,
            'Vendedor': credito.vendedor.nombre,
            'Total': int(credito.total),
            'Saldo Pendiente': int(credito.saldo_pendiente) if credito.saldo_pendiente else 0,
            'Estado': credito.estado.title(),
            'Días Transcurridos': (datetime.now() - credito.fecha).days
        })
    
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='openpyxl') as writer:
        df.to_excel(writer, sheet_name='Créditos', index=False)
    
    output.seek(0)
    
    response = make_response(output.getvalue())
    response.headers['Content-Disposition'] = f'attachment; filename=creditos_{fecha_inicio.strftime("%Y%m%d")}-{fecha_fin.strftime("%Y%m%d")}.xlsx'
    response.headers['Content-Type'] = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    
    return response
