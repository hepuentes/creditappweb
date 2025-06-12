import sys
import os
from datetime import datetime

# Agregar el directorio del proyecto al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app, db
from sqlalchemy import text

def migrate_transferencias():
    """Ejecuta la migración para agregar campos de transferencias"""
    
    app = create_app()
    
    with app.app_context():
        try:
            print("🚀 Iniciando migración de transferencias...")
            
            # 1. Agregar las nuevas columnas a la tabla ventas
            print("📝 Agregando nuevas columnas a tabla 'ventas'...")
            
            try:
                # Verificar si las columnas ya existen
                inspector = db.inspect(db.engine)
                columns = [col['name'] for col in inspector.get_columns('ventas')]
                
                if 'vendedor_original_id' not in columns:
                    db.session.execute(text("""
                        ALTER TABLE ventas 
                        ADD COLUMN vendedor_original_id INTEGER REFERENCES usuarios(id)
                    """))
                    print("  ✅ Columna 'vendedor_original_id' agregada")
                else:
                    print("  ⚠️  Columna 'vendedor_original_id' ya existe")
                
                if 'usuario_actual_id' not in columns:
                    db.session.execute(text("""
                        ALTER TABLE ventas 
                        ADD COLUMN usuario_actual_id INTEGER REFERENCES usuarios(id)
                    """))
                    print("  ✅ Columna 'usuario_actual_id' agregada")
                else:
                    print("  ⚠️  Columna 'usuario_actual_id' ya existe")
                
                if 'transferida' not in columns:
                    db.session.execute(text("""
                        ALTER TABLE ventas 
                        ADD COLUMN transferida BOOLEAN DEFAULT FALSE NOT NULL
                    """))
                    print("  ✅ Columna 'transferida' agregada")
                else:
                    print("  ⚠️  Columna 'transferida' ya existe")
                
                if 'fecha_transferencia' not in columns:
                    db.session.execute(text("""
                        ALTER TABLE ventas 
                        ADD COLUMN fecha_transferencia TIMESTAMP
                    """))
                    print("  ✅ Columna 'fecha_transferencia' agregada")
                else:
                    print("  ⚠️  Columna 'fecha_transferencia' ya existe")
                    
            except Exception as e:
                print(f"  ❌ Error agregando columnas a 'ventas': {e}")
                # Continuar, tal vez las columnas ya existan
            
            # 2. Crear la tabla de transferencias si no existe
            print("📝 Creando tabla 'transferencias_venta'...")
            
            try:
                # Verificar si la tabla ya existe
                tables = inspector.get_table_names()
                
                if 'transferencias_venta' not in tables:
                    db.session.execute(text("""
                        CREATE TABLE transferencias_venta (
                            id SERIAL PRIMARY KEY,
                            venta_id INTEGER NOT NULL REFERENCES ventas(id) ON DELETE CASCADE,
                            usuario_origen_id INTEGER NOT NULL REFERENCES usuarios(id),
                            usuario_destino_id INTEGER NOT NULL REFERENCES usuarios(id),
                            realizada_por_id INTEGER NOT NULL REFERENCES usuarios(id),
                            motivo VARCHAR(500),
                            fecha TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL
                        )
                    """))
                    print("  ✅ Tabla 'transferencias_venta' creada")
                else:
                    print("  ⚠️  Tabla 'transferencias_venta' ya existe")
                    
            except Exception as e:
                print(f"  ❌ Error creando tabla 'transferencias_venta': {e}")
            
            # 3. Crear índices para mejorar rendimiento
            print("📝 Creando índices...")
            
            try:
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_ventas_transferida 
                    ON ventas(transferida)
                """))
                
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_ventas_usuario_actual 
                    ON ventas(usuario_actual_id) 
                    WHERE usuario_actual_id IS NOT NULL
                """))
                
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_ventas_vendedor_original 
                    ON ventas(vendedor_original_id) 
                    WHERE vendedor_original_id IS NOT NULL
                """))
                
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_transferencias_venta_id 
                    ON transferencias_venta(venta_id)
                """))
                
                db.session.execute(text("""
                    CREATE INDEX IF NOT EXISTS idx_transferencias_fecha 
                    ON transferencias_venta(fecha)
                """))
                
                print("  ✅ Índices creados")
                
            except Exception as e:
                print(f"  ⚠️  Error creando índices (probablemente ya existen): {e}")
            
            # 4. Actualizar registros existentes
            print("📝 Actualizando registros existentes...")
            
            try:
                # Asegurar que todas las ventas existentes tengan transferida = False
                result = db.session.execute(text("""
                    UPDATE ventas 
                    SET transferida = FALSE 
                    WHERE transferida IS NULL
                """))
                print(f"  ✅ Registros actualizados")
                
            except Exception as e:
                print(f"  ❌ Error actualizando registros: {e}")
            
            # 5. Confirmar cambios
            db.session.commit()
            print("✅ Migración completada exitosamente!")
            
            # 6. Verificar que las columnas se crearon correctamente
            print("📝 Verificando estructura de la base de datos...")
            try:
                # Refrescar inspector después de los cambios
                inspector = db.inspect(db.engine)
                columns_after = [col['name'] for col in inspector.get_columns('ventas')]
                
                required_columns = ['vendedor_original_id', 'usuario_actual_id', 'transferida', 'fecha_transferencia']
                missing_columns = [col for col in required_columns if col not in columns_after]
                
                if missing_columns:
                    print(f"  ⚠️  Faltan columnas: {missing_columns}")
                    return False
                else:
                    print("  ✅ Todas las columnas requeridas están presentes")
                
            except Exception as e:
                print(f"  ❌ Error verificando estructura: {e}")
                return False
            
            # 7. Mostrar estadísticas solo si todo salió bien
            try:
                # Usar consulta SQL directa para evitar problemas con el modelo
                result = db.session.execute(text("SELECT COUNT(*) FROM ventas"))
                total_ventas = result.scalar()
                
                result = db.session.execute(text("SELECT COUNT(*) FROM ventas WHERE tipo = 'credito'"))
                ventas_credito = result.scalar()
                
                result = db.session.execute(text("SELECT COUNT(*) FROM ventas WHERE tipo = 'credito' AND saldo_pendiente > 0"))
                ventas_pendientes = result.scalar()
                
                print(f"""
📊 ESTADÍSTICAS DESPUÉS DE LA MIGRACIÓN:
   • Total de ventas: {total_ventas}
   • Ventas a crédito: {ventas_credito}
   • Ventas transferibles: {ventas_pendientes}
   
💡 FUNCIONALIDADES HABILITADAS:
   • Transferir ventas a crédito entre usuarios
   • Historial completo de transferencias
   • Permisos basados en transferencias
   • Reversión de transferencias (solo admin)
   
🔧 PRÓXIMOS PASOS:
   1. ✅ Blueprint ya agregado al __init__.py
   2. ✅ Enlaces de navegación ya agregados
   3. Crear controlador transferencias.py
   4. Crear vistas de transferencias
   5. Probar la funcionalidad
                """)
                
            except Exception as e:
                print(f"  ⚠️  No se pudieron obtener estadísticas: {e}")
            
        except Exception as e:
            print(f"❌ Error durante la migración: {e}")
            db.session.rollback()
            return False
        
        return True

if __name__ == "__main__":
    print("🔄 MIGRACIÓN DE TRANSFERENCIAS DE VENTAS")
    print("=" * 50)
    
    if migrate_transferencias():
        print("\n🎉 ¡Migración completada con éxito!")
        print("\nAhora puedes:")
        print("1. Crear el controlador transferencias.py")
        print("2. Crear las vistas de transferencias")
        print("3. Reiniciar la aplicación")
        print("4. ¡Empezar a usar las transferencias!")
    else:
        print("\n💥 Hubo errores durante la migración.")
        print("Revisa los mensajes anteriores y corrige los problemas.")
        sys.exit(1)