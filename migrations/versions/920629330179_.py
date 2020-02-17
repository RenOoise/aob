"""empty message

Revision ID: 920629330179
Revises: de27dc337b3e
Create Date: 2019-07-25 22:37:34.303594

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '920629330179'
down_revision = 'de27dc337b3e'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('fuel_residue', sa.Column('fuel_volume_percents', sa.Float(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('fuel_residue', 'fuel_volume_percents')
    # ### end Alembic commands ###
