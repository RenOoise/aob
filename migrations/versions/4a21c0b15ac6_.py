"""empty message

Revision ID: 4a21c0b15ac6
Revises: b584f9a07b30
Create Date: 2019-09-29 22:33:16.040874

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4a21c0b15ac6'
down_revision = 'b584f9a07b30'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('temp_azs_trucks4', sa.Column('azs_id', sa.Integer(), nullable=True))
    op.add_column('temp_azs_trucks4', sa.Column('truck_id', sa.Integer(), nullable=True))
    op.create_foreign_key(None, 'temp_azs_trucks4', 'trucks', ['truck_id'], ['id'])
    op.create_foreign_key(None, 'temp_azs_trucks4', 'azs_list', ['azs_id'], ['id'])
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_constraint(None, 'temp_azs_trucks4', type_='foreignkey')
    op.drop_constraint(None, 'temp_azs_trucks4', type_='foreignkey')
    op.drop_column('temp_azs_trucks4', 'truck_id')
    op.drop_column('temp_azs_trucks4', 'azs_id')
    # ### end Alembic commands ###
