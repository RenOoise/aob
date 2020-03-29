"""empty message

Revision ID: 5f3a47c13c28
Revises: 8b6b2107e453
Create Date: 2019-08-08 21:06:48.164723

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '5f3a47c13c28'
down_revision = '8b6b2107e453'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('fuel_realisation', sa.Column('average_week_ago', sa.Float(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('fuel_realisation', 'average_week_ago')
    # ### end Alembic commands ###
