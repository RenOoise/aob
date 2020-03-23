"""empty message

Revision ID: 8b6b2107e453
Revises: 146bfd28bef2
Create Date: 2019-08-08 20:25:21.445077

"""
import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '8b6b2107e453'
down_revision = '146bfd28bef2'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('fuel_realisation', sa.Column('fuel_realisation_week_ago', sa.Float(), nullable=True))
    op.create_unique_constraint(None, 'priority', ['tank_id'])
    op.create_unique_constraint(None, 'priority', ['priority'])
    op.drop_column('tanks', 'capacity')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('tanks', sa.Column('capacity', mysql.FLOAT(), nullable=True))
    op.drop_constraint(None, 'priority', type_='unique')
    op.drop_constraint(None, 'priority', type_='unique')
    op.drop_column('fuel_realisation', 'fuel_realisation_week_ago')
    # ### end Alembic commands ###
