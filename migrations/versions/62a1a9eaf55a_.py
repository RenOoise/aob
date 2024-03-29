"""empty message

Revision ID: 62a1a9eaf55a
Revises: 2b8000b505a3
Create Date: 2019-09-08 21:46:00.182879

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '62a1a9eaf55a'
down_revision = '2b8000b505a3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('trip_for_today',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('azs_id', sa.Integer(), nullable=True),
    sa.Column('azs_number', sa.Integer(), nullable=True),
    sa.Column('truck_id', sa.Integer(), nullable=True),
    sa.Column('truck_number', sa.String(length=60), nullable=True),
    sa.Column('trip_number', sa.Integer(), nullable=True),
    sa.Column('variant_id', sa.Integer(), nullable=True),
    sa.Column('zapolnenie', sa.String(length=200), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.Column('complete', sa.Boolean(), nullable=True),
    sa.ForeignKeyConstraint(['azs_id'], ['azs_list.id'], ),
    sa.ForeignKeyConstraint(['truck_id'], ['trucks.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('trip_for_today')
    # ### end Alembic commands ###
