import os
from datetime import datetime, timedelta
from io import BytesIO
from PIL import Image
from flask import current_app, url_for
from app import db
from app.models import Configuracion, Comision, Venta, Abono, MovimientoCaja
import logging
import base64

def format_currency(amount):
    """Formatea un monto como moneda (sin decimales)"""
    from decimal import Decimal, InvalidOperation
    
    # Obtener símbolo de moneda de la configuración
    try:
        config = Configuracion.query.first()
        moneda = config.moneda if config else "$"
    except Exception:
        moneda = "$"
        
    # Si amount es None o vacío, devolver cero formateado
    if amount is None:
        return f"{moneda} 0"
        
    # Convertir a Decimal para manejo preciso
    try:
        # Si es string, primero limpiar formato
        if isinstance(amount, str):
            # Eliminar cualquier símbolo de moneda y espacios
            amount = amount.replace(moneda, '').strip()
            # Reemplazar comas por nada (formato de miles)
            amount = amount.replace(',', '')
        
        # Convertir a Decimal
        decimal_amount = Decimal(str(amount))
        
        # Formatear sin decimales y con separador de miles
        formatted_amount = f"{int(decimal_amount):,}" if decimal_amount == int(decimal_amount) else f"{float(decimal_amount):,.2f}"
        
    except (ValueError, InvalidOperation, TypeError):
        # Si hay error de conversión, intentar el mejor esfuerzo
        try:
            formatted_amount = f"{float(amount):,.2f}"
        except:
            formatted_amount = str(amount)
    
    # Retornar con el símbolo de moneda
    return f"{moneda} {formatted_amount}"


def calcular_comision(monto, usuario_id, venta_id=None, abono_id=None):
    """Calcula la comisión sobre un monto para un usuario según su rol"""
    from app.models import Usuario
    
    config = Configuracion.query.first()
    usuario = Usuario.query.get(usuario_id)
    
    if not config or not usuario:
        return 0

    # Determinar porcentaje según el rol del usuario
    if usuario.rol == 'vendedor':
        porcentaje = (config.porcentaje_comision_vendedor or 5) / 100
    elif usuario.rol == 'cobrador':
        porcentaje = (config.porcentaje_comision_cobrador or 3) / 100
    else:
        porcentaje = (config.porcentaje_comision_vendedor or 5) / 100  # Por defecto

    monto_comision = monto * porcentaje
    periodo = config.periodo_comision

    # Registrar la comisión
    comision = Comision(
        usuario_id=usuario_id,
        monto_base=monto,
        porcentaje=config.porcentaje_comision_vendedor if usuario.rol == 'vendedor' else config.porcentaje_comision_cobrador,
        monto_comision=monto_comision,
        periodo=periodo,
        venta_id=venta_id,
        abono_id=abono_id
    )

    db.session.add(comision)
    db.session.commit()

    return monto_comision


def get_comisiones_periodo(usuario_id=None, fecha_inicio=None, fecha_fin=None):
    """Obtiene las comisiones para un período determinado"""
    try:
        if not fecha_inicio:
            try:
                config = Configuracion.query.first()
                periodo = config.periodo_comision if config else 'mensual'
            except Exception:
                periodo = 'mensual'

            today = datetime.now()
            if periodo == 'mensual':
                fecha_inicio = datetime(today.year, today.month, 1)
                if today.month == 12:
                    fecha_fin = datetime(today.year + 1, 1, 1) - timedelta(days=1)
                else:
                    fecha_fin = datetime(today.year, today.month + 1, 1) - timedelta(days=1)
            else:  # quincenal
                if today.day <= 15:
                    fecha_inicio = datetime(today.year, today.month, 1)
                    fecha_fin = datetime(today.year, today.month, 15)
                else:
                    fecha_inicio = datetime(today.year, today.month, 16)
                    if today.month == 12:
                        fecha_fin = datetime(today.year + 1, 1, 1) - timedelta(days=1)
                    else:
                        fecha_fin = datetime(today.year, today.month + 1, 1) - timedelta(days=1)

        # Crear nueva sesión para evitar problemas de transacciones abortadas
        query = Comision.query.filter(
            Comision.fecha_generacion >= fecha_inicio,
            Comision.fecha_generacion <= fecha_fin
        )

        if usuario_id:
            query = query.filter_by(usuario_id=usuario_id)

        # Ejecutar la consulta con manejo de errores mejorado
        try:
            result = query.all()
            return result
        except Exception as db_error:
            # Si hay error de transacción, hacer rollback y reintentar
            db.session.rollback()
            print(f"Error en consulta de comisiones, reintentando: {db_error}")
            
            # Reintentar con nueva consulta
            query = Comision.query.filter(
                Comision.fecha_generacion >= fecha_inicio,
                Comision.fecha_generacion <= fecha_fin
            )
            if usuario_id:
                query = query.filter_by(usuario_id=usuario_id)
            
            return query.all()
            
    except Exception as e:
        print(f"Error en get_comisiones_periodo: {e}")
        # Hacer rollback en caso de error
        db.session.rollback()
        return []


def registrar_movimiento_caja(
    caja_id,
    tipo,
    monto,
    concepto=None,
    venta_id=None,
    abono_id=None,
    caja_destino_id=None
):
    """Registra un movimiento en caja y actualiza saldos"""
    from app.models import Caja, MovimientoCaja
    from app import db
    from datetime import datetime
    import logging
    from sqlalchemy import inspect

    logging.info(
        f"Registrando movimiento en caja {caja_id}: {tipo} por ${monto} - {concepto}"
    )

    try:
        caja = Caja.query.get(caja_id)
        if not caja:
            raise ValueError(f"Caja con ID {caja_id} no encontrada")

        # Verificar si las columnas necesarias existen en la tabla
        try:
            inspector = inspect(db.engine)
            columns = inspector.get_columns('movimiento_caja')
            column_names = [col['name'] for col in columns]
        except Exception:
            # Si falla, asumimos que todas las columnas existen
            column_names = [
                'caja_id', 'tipo', 'monto', 'fecha', 'descripcion',
                'venta_id', 'abono_id', 'caja_destino_id'
            ]

        # Crear el movimiento con los parámetros básicos
        movimiento = MovimientoCaja(
            caja_id=caja_id,
            tipo=tipo,
            monto=monto,
            fecha=datetime.utcnow(),
            descripcion=concepto
        )

        # Agregar campos adicionales solo si existen
        if 'venta_id' in column_names and venta_id is not None:
            movimiento.venta_id = venta_id
        if 'abono_id' in column_names and abono_id is not None:
            movimiento.abono_id = abono_id
        if 'caja_destino_id' in column_names and caja_destino_id is not None:
            movimiento.caja_destino_id = caja_destino_id

        # Actualizar saldo de la caja
        if tipo == 'entrada':
            caja.saldo_actual += monto
        elif tipo == 'salida':
            caja.saldo_actual -= monto
        elif tipo == 'transferencia' and caja_destino_id:
            caja.saldo_actual -= monto
            caja_destino = Caja.query.get(caja_destino_id)
            if not caja_destino:
                raise ValueError(
                    f"Caja destino con ID {caja_destino_id} no encontrada"
                )
            caja_destino.saldo_actual += monto

            # Crear movimiento en la caja destino si la columna existe
            if 'caja_destino_id' in column_names:
                movimiento_destino = MovimientoCaja(
                    caja_id=caja_destino_id,
                    tipo='entrada',
                    monto=monto,
                    fecha=datetime.utcnow(),
                    descripcion=f"Transferencia desde {caja.nombre}"
                )
                movimiento_destino.caja_destino_id = caja_id
                db.session.add(movimiento_destino)

        db.session.add(movimiento)
        db.session.commit()

        logging.info(f"Movimiento registrado exitosamente: ID {movimiento.id}")
        return movimiento

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error al registrar movimiento en caja: {e}")
        # No propagamos el error para no interrumpir la venta/abono
        return None


# FUNCIONES PARA COMPARTIR PDFS

def get_venta_pdf_descarga_url(venta_id):
    """Genera una URL para descarga directa del PDF de venta sin autenticación"""
    # Importar aquí para evitar importaciones circulares
    import hashlib
    from flask import request
    
    try:
        # Generar token simple
        secret_key = 'creditmobileapp2025'
        message = f"venta_{venta_id}_{secret_key}"
        token = hashlib.sha256(message.encode()).hexdigest()[:20]
        
        # Construir URL con el host actual
        host = request.host_url.rstrip('/')
        path = f"/public/venta/{venta_id}/descargar/{token}"
        public_url = f"{host}{path}"
        
        return public_url
    except Exception as e:
        current_app.logger.error(f"Error generando URL para venta {venta_id}: {e}")
        return None

def get_abono_pdf_descarga_url(abono_id):
    """Genera una URL para descarga directa del PDF de abono sin autenticación"""
    # Importar aquí para evitar importaciones circulares  
    import hashlib
    from flask import request
    
    try:
        # Generar token simple
        secret_key = 'creditmobileapp2025'
        message = f"abono_{abono_id}_{secret_key}"
        token = hashlib.sha256(message.encode()).hexdigest()[:20]
        
        # Construir URL con el host actual
        host = request.host_url.rstrip('/')
        path = f"/public/abono/{abono_id}/descargar/{token}"
        public_url = f"{host}{path}"
        
        return public_url
    except Exception as e:
        current_app.logger.error(f"Error generando URL para abono {abono_id}: {e}")
        return None

def pdf_to_data_url(pdf_bytes):
    """Convierte un PDF en bytes a una URL de datos (data URL)"""
    try:
        # Verificar que pdf_bytes sea efectivamente bytes
        if not isinstance(pdf_bytes, bytes):
            current_app.logger.error(f"Error: pdf_bytes no es de tipo bytes, es {type(pdf_bytes)}")
            return None
            
        # Codificar los bytes del PDF en base64
        pdf_base64 = base64.b64encode(pdf_bytes).decode('utf-8')
        
        # Crear la data URL con el formato correcto
        data_url = f"data:application/pdf;base64,{pdf_base64}"
        
        return data_url
    except Exception as e:
        current_app.logger.error(f"Error creando data URL: {e}")
        return None

def get_venta_pdf_data_url(venta_id):
    """Genera el PDF de una venta y lo convierte a data URL"""
    from app.models import Venta
    from app.pdf.venta import generar_pdf_venta
    
    try:
        # Obtener la venta
        venta = Venta.query.get(venta_id)
        if not venta:
            current_app.logger.error(f"Venta {venta_id} no encontrada")
            return None
            
        # Generar PDF
        pdf_bytes = generar_pdf_venta(venta)
        if not pdf_bytes:
            current_app.logger.error(f"Error: generar_pdf_venta devolvió valor nulo")
            return None
            
        # Convertir a data URL
        return pdf_to_data_url(pdf_bytes)
        
    except Exception as e:
        current_app.logger.error(f"Error generando data URL para venta {venta_id}: {e}")
        return None

def get_abono_pdf_data_url(abono_id):
    """Genera el PDF de un abono y lo convierte a data URL"""
    from app.models import Abono
    from app.pdf.abono import generar_pdf_abono
    
    try:
        # Obtener el abono
        abono = Abono.query.get(abono_id)
        if not abono:
            current_app.logger.error(f"Abono {abono_id} no encontrado")
            return None
            
        # Generar PDF
        pdf_bytes = generar_pdf_abono(abono)
        if not pdf_bytes:
            current_app.logger.error(f"Error: generar_pdf_abono devolvió valor nulo")
            return None
            
        # Convertir a data URL
        return pdf_to_data_url(pdf_bytes)
        
    except Exception as e:
        current_app.logger.error(f"Error generando data URL para abono {abono_id}: {e}")
        return None

def shorten_url(long_url):
    """Acorta una URL larga usando TinyURL (servicio gratuito sin API key)"""
    try:
        import requests
        # Usar TinyURL sin necesidad de API key
        api_url = f"https://tinyurl.com/api-create.php?url={long_url}"
        response = requests.get(api_url, timeout=5)  # Añadir timeout de 5 segundos
        
        if response.status_code == 200:
            return response.text
        else:
            current_app.logger.warning(f"Error acortando URL: {response.status_code}")
            return long_url  # Devolver URL original si hay error
    except ImportError:
        current_app.logger.warning("No se pudo importar la biblioteca 'requests'. Usando URL original.")
        return long_url  # Devolver URL original si no está disponible requests
    except Exception as e:
        current_app.logger.error(f"Error en servicio de acortamiento de URL: {e}")
        return long_url  # Devolver URL original en caso de cualquier error
