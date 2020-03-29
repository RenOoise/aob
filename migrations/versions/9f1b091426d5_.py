"""empty message

Revision ID: 9f1b091426d5
Revises: 3d6ace77bfe3
Create Date: 2019-09-18 21:23:36.164734

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '9f1b091426d5'
down_revision = '3d6ace77bfe3'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('temp_azs_trucks2', sa.Column('will_it_meld', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('temp_azs_trucks2', 'will_it_meld')
    # ### end Alembic commands ###
