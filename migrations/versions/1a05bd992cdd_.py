"""empty message

Revision ID: 1a05bd992cdd
Revises: 59a6d8261bc0
Create Date: 2019-09-18 22:01:49.044630

"""
import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision = '1a05bd992cdd'
down_revision = '59a6d8261bc0'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('temp_azs_trucks2', sa.Column('is_variant_sliv_good', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('temp_azs_trucks2', 'is_variant_sliv_good')
    # ### end Alembic commands ###
