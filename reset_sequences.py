# Crear un nuevo archivo reset_sequences_immediate.py

from app import create_app, db
from sqlalchemy import text, inspect

app = create_app()

with app.app_context():
    print("== REPARANDO SECUENCIAS DE TODAS LAS TABLAS ==")
    
    try:
        with db.engine.connect() as connection:
            # Obtener tablas
            tables = connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")).fetchall()
            
            for table_info in tables:
                table_name = table_info[0]
                
                # Verificar que la tabla tiene columna id
                has_id = connection.execute(text(
                    f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}' AND column_name = 'id'"
                )).fetchone() is not None
                
                if has_id:
                    # Obtener valor máximo id
                    max_id = connection.execute(text(f"SELECT MAX(id) FROM {table_name}")).fetchone()[0] or 0
                    
                    # Resetear la secuencia
                    connection.execute(text(
                        f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), {max_id + 1}, false)"
                    ))
                    
                    print(f"  ✓ Secuencia reparada para tabla: {table_name} (próximo ID: {max_id + 1})")
        
        print("¡Secuencias reparadas correctamente!")
        
    except Exception as e:
        print(f"ERROR: {e}")
