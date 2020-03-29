"""empty message

Revision ID: 7314578efe0a
Revises: 4b4bf4c445fd
Create Date: 2019-08-06 14:13:28.677886

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '7314578efe0a'
down_revision = '4b4bf4c445fd'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.add_column('trip', sa.Column('time_from_before_lunch', sa.Time(), nullable=True))
    op.add_column('trip', sa.Column('time_to_before_lunch', sa.Time(), nullable=True))
    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    op.drop_column('trip', 'time_to_before_lunch')
    op.drop_column('trip', 'time_from_before_lunch')
    # ### end Alembic commands ###
