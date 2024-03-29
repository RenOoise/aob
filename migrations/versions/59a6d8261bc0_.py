"""empty message

Revision ID: 59a6d8261bc0
Revises: 158f7c933ca4
Create Date: 2019-09-18 21:41:30.136088

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

# revision identifiers, used by Alembic.
revision = '59a6d8261bc0'
down_revision = '158f7c933ca4'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('temp_azs_trucks2', 'will_it_meld')
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('temp_azs_trucks2', sa.Column('will_it_meld', mysql.TINYINT(display_width=1), autoincrement=False, nullable=True))
    # ### end Alembic commands ###
