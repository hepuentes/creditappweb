"""Agrega campo porcentaje_comision a Configuracion"""

from alembic import op
import sqlalchemy as sa

# Identificadores de la migración
revision = 'efc506d4f583'  # El id de este archivo
down_revision = None       # Primera migración
branch_labels = None
depends_on = None

def upgrade():
    op.add_column('configuraciones', sa.Column('porcentaje_comision', sa.Float(), nullable=True))

def downgrade():
    op.drop_column('configuraciones', 'porcentaje_comision')
