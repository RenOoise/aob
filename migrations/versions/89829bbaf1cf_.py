"""empty message

Revision ID: 89829bbaf1cf
Revises: 917f5a5ff79a
Create Date: 2019-08-15 21:25:52.482565

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '89829bbaf1cf'
down_revision = '917f5a5ff79a'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('priority_buf',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('azs_id', sa.Integer(), nullable=True),
    sa.Column('tank_id', sa.Integer(), nullable=True),
    sa.Column('day_stock', sa.Float(), nullable=True),
    sa.Column('priority', sa.Integer(), nullable=True),
    sa.Column('table_priority', sa.Integer(), nullable=True),
    sa.Column('timestamp', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['azs_id'], ['azs_list.id'], ),
    sa.ForeignKeyConstraint(['table_priority'], ['priority_list.id'], ),
    sa.ForeignKeyConstraint(['tank_id'], ['tanks.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('priority'),
    sa.UniqueConstraint('tank_id')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('priority_buf')
    # ### end Alembic commands ###
