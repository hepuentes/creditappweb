# auto_migrate.py 
import os
import shutil
from sqlalchemy import text, inspect
from app import create_app, db
from app.models import (Usuario, Cliente, Venta, Credito, Abono, Caja, 
                        MovimientoCaja, CreditoVenta, DetalleVenta, 
                        Comision, Configuracion, Producto)
import logging

logging.basicConfig(level=logging.INFO, 
                   format='%(asctime)s [AUTO-MIGRATE] %(levelname)s: %(message)s')
logger = logging.getLogger(__name__)

app = create_app()

with app.app_context():
    logger.info("=== INICIANDO PROCESO DE REPARACIÓN INTEGRAL DE LA BASE DE DATOS ===")
    
    try:
        # PASO 1: Reparar las secuencias de IDs en todas las tablas
        logger.info("Reparando secuencias de autoincremento...")
        
        with db.engine.connect() as connection:
            # Obtener todas las tablas de la base de datos
            tablas = connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).fetchall()
            
            for tabla_info in tablas:
                tabla = tabla_info[0]
                try:
                    # Verificar si la tabla tiene columna ID
                    result = connection.execute(text(
                        f"SELECT column_name FROM information_schema.columns WHERE table_name = '{tabla}' AND column_name = 'id'"
                    )).fetchone()
                    
                    if result:
                        # Obtener el valor máximo de ID
                        max_id = connection.execute(text(f"SELECT MAX(id) FROM {tabla}")).scalar() or 0
                        
                        # Resetear la secuencia al valor máximo + 1
                        connection.execute(text(
                            f"SELECT setval(pg_get_serial_sequence('{tabla}', 'id'), {max_id + 1}, false)"
                        ))
                        logger.info(f"  ✓ Secuencia reparada para tabla: {tabla} (próximo ID: {max_id + 1})")
                except Exception as e:
                    logger.error(f"  ✗ Error al reparar secuencia para tabla {tabla}: {e}")
        
        # PASO 2: Verificar y reparar la estructura de las tablas
        logger.info("\nVerificando estructura de tablas críticas...")
        
        # Tabla movimiento_caja
        logger.info("Verificando tabla 'movimiento_caja'...")
        inspector = inspect(db.engine)
        
        if 'movimiento_caja' in inspector.get_table_names():
            columnas = [c['name'] for c in inspector.get_columns('movimiento_caja')]
            
            with db.engine.begin() as connection:
                # Verificar columna venta_id
                if 'venta_id' not in columnas:
                    logger.info("  ✓ Agregando columna 'venta_id' a movimiento_caja...")
                    connection.execute(text("ALTER TABLE movimiento_caja ADD COLUMN venta_id INTEGER"))
                    # Intentar agregar foreign key si es posible
                    try:
                        connection.execute(text(
                            "ALTER TABLE movimiento_caja ADD CONSTRAINT fk_movimiento_venta " +
                            "FOREIGN KEY (venta_id) REFERENCES ventas(id)"
                        ))
                        logger.info("  ✓ Foreign key para venta_id agregada")
                    except Exception as e:
                        logger.warning(f"    No se pudo agregar foreign key para venta_id: {e}")
                
                # Verificar columna abono_id
                if 'abono_id' not in columnas:
                    logger.info("  ✓ Agregando columna 'abono_id' a movimiento_caja...")
                    connection.execute(text("ALTER TABLE movimiento_caja ADD COLUMN abono_id INTEGER"))
                    # Intentar agregar foreign key si es posible
                    try:
                        connection.execute(text(
                            "ALTER TABLE movimiento_caja ADD CONSTRAINT fk_movimiento_abono " +
                            "FOREIGN KEY (abono_id) REFERENCES abonos(id)"
                        ))
                        logger.info("  ✓ Foreign key para abono_id agregada")
                    except Exception as e:
                        logger.warning(f"    No se pudo agregar foreign key para abono_id: {e}")
                
                # Verificar columna caja_destino_id
                if 'caja_destino_id' not in columnas:
                    logger.info("  ✓ Agregando columna 'caja_destino_id' a movimiento_caja...")
                    connection.execute(text("ALTER TABLE movimiento_caja ADD COLUMN caja_destino_id INTEGER"))
                    # Intentar agregar foreign key si es posible
                    try:
                        connection.execute(text(
                            "ALTER TABLE movimiento_caja ADD CONSTRAINT fk_movimiento_caja_destino " +
                            "FOREIGN KEY (caja_destino_id) REFERENCES cajas(id)"
                        ))
                        logger.info("  ✓ Foreign key para caja_destino_id agregada")
                    except Exception as e:
                        logger.warning(f"    No se pudo agregar foreign key para caja_destino_id: {e}")
        else:
            logger.warning("La tabla 'movimiento_caja' no existe. Se creará durante db.create_all()")
        
        # Tabla comisiones - Añadir nuevos campos
        logger.info("Verificando tabla 'comisiones'...")
        
        if 'comisiones' in inspector.get_table_names():
            columnas = [c['name'] for c in inspector.get_columns('comisiones')]
            
            with db.engine.begin() as connection:
                # Verificar columna venta_id
                if 'venta_id' not in columnas:
                    logger.info("  ✓ Agregando columna 'venta_id' a comisiones...")
                    connection.execute(text("ALTER TABLE comisiones ADD COLUMN venta_id INTEGER"))
                    # Intentar agregar foreign key si es posible
                    try:
                        connection.execute(text(
                            "ALTER TABLE comisiones ADD CONSTRAINT fk_comision_venta " +
                            "FOREIGN KEY (venta_id) REFERENCES ventas(id)"
                        ))
                        logger.info("  ✓ Foreign key para venta_id agregada a comisiones")
                    except Exception as e:
                        logger.warning(f"    No se pudo agregar foreign key para venta_id en comisiones: {e}")
                
                # Verificar columna abono_id
                if 'abono_id' not in columnas:
                    logger.info("  ✓ Agregando columna 'abono_id' a comisiones...")
                    connection.execute(text("ALTER TABLE comisiones ADD COLUMN abono_id INTEGER"))
                    # Intentar agregar foreign key si es posible
                    try:
                        connection.execute(text(
                            "ALTER TABLE comisiones ADD CONSTRAINT fk_comision_abono " +
                            "FOREIGN KEY (abono_id) REFERENCES abonos(id)"
                        ))
                        logger.info("  ✓ Foreign key para abono_id agregada a comisiones")
                    except Exception as e:
                        logger.warning(f"    No se pudo agregar foreign key para abono_id en comisiones: {e}")
        else:
            logger.warning("La tabla 'comisiones' no existe. Se creará durante db.create_all()")
        
        # PASO 3: Crear tablas faltantes o reparar inconsistencias
        logger.info("\nCreando tablas faltantes y verificando relaciones...")
        db.create_all()
        
        # PASO ADICIONAL: Eliminar la restricción problemática de la tabla abonos
        try:
            with db.engine.begin() as connection:
                # Eliminar la restricción check_credito_reference que causa problemas
                connection.execute(text(
                    "ALTER TABLE abonos DROP CONSTRAINT IF EXISTS check_credito_reference"
                ))
                logger.info("  ✓ Restricción check_credito_reference eliminada de la tabla abonos")
                
                # Asegurar que ciertos campos no sean nulos en la tabla abonos
                connection.execute(text(
                    "ALTER TABLE abonos ALTER COLUMN cobrador_id SET NOT NULL"
                ))
                connection.execute(text(
                    "ALTER TABLE abonos ALTER COLUMN caja_id SET NOT NULL"
                ))
                logger.info("  ✓ Campos obligatorios en la tabla abonos actualizados")
        except Exception as e:
            logger.error(f"  ✗ Error al modificar la tabla abonos: {e}")
        
        # PASO 4: Corregir datos incongruentes
        logger.info("\nVerificando y corrigiendo datos incongruentes...")
        
        # Corregir ventas a crédito con saldo_pendiente=0 que deberían estar pagadas
        try:
            with db.engine.begin() as connection:
                connection.execute(text(
                    "UPDATE ventas SET estado = 'pagado' " +
                    "WHERE tipo = 'credito' AND (saldo_pendiente IS NULL OR saldo_pendiente <= 0)"
                ))
                logger.info("  ✓ Ventas a crédito con saldo 0 marcadas como pagadas")
                
                # Asegurar que todas las ventas tienen estado
                connection.execute(text(
                    "UPDATE ventas SET estado = 'pendiente' WHERE estado IS NULL AND tipo = 'credito'"
                ))
                connection.execute(text(
                    "UPDATE ventas SET estado = 'pagado' WHERE estado IS NULL AND tipo = 'contado'"
                ))
                logger.info("  ✓ Ventas sin estado actualizado correctamente")
        except Exception as e:
            logger.error(f"  ✗ Error al corregir datos incongruentes: {e}")
        
        # PASO 5: Validar integridad referencial
        logger.info("\nValidando integridad referencial...")
        
        try:
            # Verificar que los clientes existen
            ventas_sin_cliente = db.session.query(Venta).filter(
                ~Venta.cliente_id.in_(db.session.query(Cliente.id))
            ).all()
            
            if ventas_sin_cliente:
                logger.warning(f"  ! Se encontraron {len(ventas_sin_cliente)} ventas con clientes inexistentes")
                # No eliminamos automáticamente para evitar pérdida de datos
            
            # Verificar que los vendedores existen
            ventas_sin_vendedor = db.session.query(Venta).filter(
                ~Venta.vendedor_id.in_(db.session.query(Usuario.id))
            ).all()
            
            if ventas_sin_vendedor:
                logger.warning(f"  ! Se encontraron {len(ventas_sin_vendedor)} ventas con vendedores inexistentes")
                # No eliminamos automáticamente para evitar pérdida de datos
            
        except Exception as e:
            logger.error(f"  ✗ Error al validar integridad referencial: {e}")
        
        # PASO 6: Verificar y actualizar tabla configuraciones
        logger.info("\nVerificando tabla 'configuraciones'...")
        
        try:
            with db.engine.begin() as connection:
                # Verificar si las columnas existen
                result = connection.execute(text("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'configuraciones'
                """))
                existing_columns = [row[0] for row in result.fetchall()]
                
                # Columnas que deben existir
                required_columns = {
                    'porcentaje_comision_vendedor': 'INTEGER DEFAULT 5',
                    'porcentaje_comision_cobrador': 'INTEGER DEFAULT 3',
                    'periodo_comision': 'VARCHAR(20) DEFAULT \'mensual\''
                }
                
                # Agregar columnas faltantes
                for column_name, column_definition in required_columns.items():
                    if column_name not in existing_columns:
                        connection.execute(text(f"""
                            ALTER TABLE configuraciones 
                            ADD COLUMN {column_name} {column_definition}
                        """))
                        logger.info(f"  ✓ Columna {column_name} agregada a configuraciones")
                    else:
                        logger.info(f"  ✓ Columna {column_name} ya existe en configuraciones")
                
                # Verificar si existe algún registro de configuración
                config_count = connection.execute(text("SELECT COUNT(*) FROM configuraciones")).scalar()
                
                if config_count == 0:
                    # Crear registro de configuración inicial
                    connection.execute(text("""
                        INSERT INTO configuraciones (
                            nombre_empresa, direccion, telefono, logo, iva, moneda,
                            porcentaje_comision_vendedor, porcentaje_comision_cobrador,
                            periodo_comision, min_password
                        ) VALUES (
                            'CreditApp', 'Dirección de la empresa', '123456789', NULL, 19, '$',
                            5, 3, 'mensual', 6
                        )
                    """))
                    logger.info("  ✓ Registro de configuración inicial creado")
        except Exception as e:
            logger.error(f"  ✗ Error al verificar/actualizar tabla configuraciones: {e}")
        
        logger.info("=== PROCESO DE REPARACIÓN DE BASE DE DATOS COMPLETADO ===")
        
    except Exception as e:
        logger.error(f"ERROR GENERAL EN AUTO-MIGRATE: {e}")
        # No hacemos raise para evitar que falle el arranque de la aplicación
        logger.error("A pesar del error, se intentará iniciar la aplicación.")
