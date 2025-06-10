# migrate_abono_to_integer.py
from app import create_app, db
from app.models import Abono
from decimal import Decimal

def migrate_abono_monto_to_integer():
    app = create_app()
    
    with app.app_context():
        try:
            print("Iniciando migración de montos de abonos...")
            
            abonos = Abono.query.all()
            print(f"Encontrados {len(abonos)} abonos para migrar")
            
            if not abonos:
                print("No hay abonos para migrar")
                return
            
            for abono in abonos:
                if isinstance(abono.monto, Decimal):
                    nuevo_monto = int(abono.monto)
                    print(f"Abono #{abono.id}: {abono.monto} -> {nuevo_monto}")
                    
                    db.session.execute(
                        "UPDATE abonos SET monto = :nuevo_monto WHERE id = :abono_id",
                        {"nuevo_monto": nuevo_monto, "abono_id": abono.id}
                    )
                else:
                    print(f"Abono #{abono.id}: {abono.monto} (ya es {type(abono.monto)})")
            
            db.session.commit()
            print("Migración completada exitosamente!")
            
        except Exception as e:
            db.session.rollback()
            print(f"Error durante la migración: {e}")
            raise

if __name__ == "__main__":
    migrate_abono_monto_to_integer()