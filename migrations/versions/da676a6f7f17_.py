"""empty message

Revision ID: da676a6f7f17
Revises: b84d1fbb2a56
Create Date: 2019-09-16 20:39:06.510793

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'da676a6f7f17'
down_revision = 'b84d1fbb2a56'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_index(op.f('ix_fuel_realisation_tank_id'), 'fuel_realisation', ['tank_id'], unique=False)
    op.create_index(op.f('ix_fuel_residue_azs_id'), 'fuel_residue', ['azs_id'], unique=False)
    op.create_index(op.f('ix_tanks_azs_id'), 'tanks', ['azs_id'], unique=False)
    op.create_index(op.f('ix_tanks_id'), 'tanks', ['id'], unique=False)
    op.create_index(op.f('ix_temp_azs_trucks_variant_id'), 'temp_azs_trucks', ['variant_id'], unique=False)
    op.create_index(op.f('ix_temp_azs_trucks2_variant'), 'temp_azs_trucks2', ['variant'], unique=False)
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_index(op.f('ix_temp_azs_trucks2_variant'), table_name='temp_azs_trucks2')
    op.drop_index(op.f('ix_temp_azs_trucks_variant_id'), table_name='temp_azs_trucks')
    op.drop_index(op.f('ix_tanks_id'), table_name='tanks')
    op.drop_index(op.f('ix_tanks_azs_id'), table_name='tanks')
    op.drop_index(op.f('ix_fuel_residue_azs_id'), table_name='fuel_residue')
    op.drop_index(op.f('ix_fuel_realisation_tank_id'), table_name='fuel_realisation')
    # ### end Alembic commands ###
