"""empty message

Revision ID: a13de9510099
Revises: 082458eb0b32
Create Date: 2019-07-28 20:09:47.905226

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a13de9510099'
down_revision = '082458eb0b32'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('trucks', sa.Column('active', sa.Boolean(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('trucks', 'active')
    # ### end Alembic commands ###
