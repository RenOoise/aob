"""empty message

Revision ID: fd044edabc7d
Revises: ae89a89fde9c
Create Date: 2020-02-02 20:28:45.080736

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fd044edabc7d'
down_revision = 'ae89a89fde9c'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('result', sa.Column('trip_number', sa.Integer(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('result', 'trip_number')
    # ### end Alembic commands ###