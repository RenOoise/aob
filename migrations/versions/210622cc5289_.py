"""empty message

Revision ID: 210622cc5289
Revises: 4a21c0b15ac6
Create Date: 2019-10-06 12:43:52.590343

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '210622cc5289'
down_revision = '4a21c0b15ac6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('temp_azs_trucks', sa.Column('cells_50', sa.Integer(), nullable=True))
    op.add_column('temp_azs_trucks', sa.Column('cells_92', sa.Integer(), nullable=True))
    op.add_column('temp_azs_trucks', sa.Column('cells_95', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('temp_azs_trucks', 'cells_95')
    op.drop_column('temp_azs_trucks', 'cells_92')
    op.drop_column('temp_azs_trucks', 'cells_50')
    # ### end Alembic commands ###
