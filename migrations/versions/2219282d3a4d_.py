"""empty message

Revision ID: 2219282d3a4d
Revises: 0864eeafa2c6
Create Date: 2019-12-24 20:55:58.659541

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '2219282d3a4d'
down_revision = '0864eeafa2c6'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('global_settings_params', sa.Column('active', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('global_settings_params', 'active')
    # ### end Alembic commands ###
