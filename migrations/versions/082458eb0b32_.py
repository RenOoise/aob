"""empty message

Revision ID: 082458eb0b32
Revises: ddb8f48a2e50
Create Date: 2019-07-27 00:28:49.733990

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '082458eb0b32'
down_revision = 'ddb8f48a2e50'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('trip',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('distance', sa.Integer(), nullable=True),
    sa.Column('time_to', sa.Time(), nullable=True),
    sa.Column('time_from', sa.Time(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.add_column('trucks', sa.Column('weight', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('trucks', 'weight')
    op.drop_table('trip')
    # ### end Alembic commands ###
