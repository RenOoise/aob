"""empty message

Revision ID: c048f59f6de8
Revises: ec04a93ebecf
Create Date: 2019-07-15 18:42:17.109085

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c048f59f6de8'
down_revision = 'ec04a93ebecf'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.create_table('azs_systems',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('type', sa.String(length=40), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('type')
    )
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_table('azs_systems')
    # ### end Alembic commands ###
